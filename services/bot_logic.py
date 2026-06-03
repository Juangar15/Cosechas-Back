from datetime import datetime, timezone
from config import supabase, EMAIL_USER, EMAIL_JEFE, EMAIL_COORD_SAC, EMAIL_CAPACITADORA, EMAIL_SISTEMAS, EMAIL_GERENCIA_JURIDICA
from services.email_service import enviar_correo_pqrs_franquiciado, enviar_correo_pqrs_interno, enviar_correo_nueva_franquicia
from services.location_service import encontrar_sede_mas_cercana

def procesar_mensaje_inteligente(texto_usuario: str, celular: str):
    texto = texto_usuario.lower().strip()
    botones_bot = None
    documento_bot = None
    
    LIMITE_INACTIVIDAD_HORAS = 2
    
    # --- PASO A: RECUPERAR O CREAR LA SESIÓN EN LA BASE DE DATOS ---
    try:
        res_sesion = supabase.table("sesiones_bot").select("*").eq("celular", celular).execute()
        if len(res_sesion.data) == 0:
            estado_actual = "menu_principal"
            datos_pqrs = {}
            supabase.table("sesiones_bot").insert({
                "celular": celular, "estado": estado_actual, "datos_pqrs": datos_pqrs
            }).execute()
        else:
            sesion = res_sesion.data[0]
            estado_actual = sesion["estado"]
            datos_pqrs = sesion["datos_pqrs"]
            fecha_act_str = sesion.get("fecha_actualizacion")
            
            if fecha_act_str and estado_actual != "menu_principal":
                try:
                    fecha_limpia = datetime.fromisoformat(fecha_act_str[:19]).replace(tzinfo=timezone.utc)
                    ahora = datetime.now(timezone.utc)
                    diferencia_horas = (ahora - fecha_limpia).total_seconds() / 3600
                    
                    if diferencia_horas >= LIMITE_INACTIVIDAD_HORAS:
                        print(f"⏰ Sesión expirada por inactividad ({diferencia_horas:.2f} horas). Reseteando...")
                        estado_actual = "menu_principal"
                        datos_pqrs = {}
                except Exception as error_tiempo:
                    print("Error al calcular expiración de tiempo:", error_tiempo)
                    
    except Exception as e:
        return "Servidores en mantenimiento. Escribe 'Hola' en un momento.", None, None

    # --- INTERCEPTOR GLOBAL DE NAVEGACIÓN Y CIERRE ---
    if texto in ["volver", "atras", "cancelar", "menú principal"] and estado_actual not in ["menu_principal", "esperando_terminos"]:
        estado_actual = "menu_opciones"
        datos_pqrs = {} 
        try:
            supabase.table("sesiones_bot").update({
                "estado": estado_actual, "datos_pqrs": datos_pqrs, "fecha_actualizacion": datetime.now(timezone.utc).isoformat()
            }).eq("celular", celular).execute()
        except Exception as e:
            pass
        return "Menú Principal 🥤. Por favor, abre la lista y elige una opción:", {
            "tipo": "lista", "boton": "Seleccionar Opción",
            "opciones": ["Menú y Precios", "Radicar PQRS", "Domicilios", "Hoja de Vida", "Franquicias Col", "Franquicias Ext"]
        }, None

    if texto in ["finalizar", "terminar", "cerrar", "gracias", "chao", "adios"] and estado_actual != "menu_principal":
        estado_actual = "menu_principal"
        datos_pqrs = {}
        try:
            supabase.table("sesiones_bot").update({
                "estado": estado_actual, "datos_pqrs": datos_pqrs, "fecha_actualizacion": datetime.now(timezone.utc).isoformat()
            }).eq("celular", celular).execute()
        except Exception as e:
            pass
        return "¡Con gusto! Sesión finalizada con éxito. Cuando desees comunicarte nuevamente con Cosechas, solo escribe 'Hola'. ¡Que tengas un feliz día! 🌱🥤", None, None

    respuesta_bot = "Lo siento, ocurrió un error interno. Escribe 'Hola' para reiniciar."

    # --- PASO B: MÁQUINA DE ESTADOS LÓGICOS ---
    if estado_actual == "menu_principal":
        if "hola" in texto or "menu" in texto:
            estado_actual = "esperando_terminos"
            respuesta_bot = (
                "¡Hola! Bienvenido al asistente virtual de Cosechas 🥤.\n\n"
                "Para garantizar la seguridad de tus datos, "
                "por favor conoce nuestra Política de Tratamiento de Datos aquí:\n"
                "👉 https://www.cosechasexpress.com/politica-de-treatment-de-datos/\n\n"
                "¿Aceptas la política para continuar?"
            )
            botones_bot = ["Aceptar", "Rechazar"]
        else:
            respuesta_bot = "¡Hola! Por favor escribe 'Hola' para iniciar el asistente de Cosechas."

    elif estado_actual == "esperando_terminos":
        if texto == "aceptar":
            estado_actual = "menu_opciones"
            respuesta_bot = "¡Perfecto! Gracias por confiar en nosotros. Por favor, despliega la lista y selecciona cómo te podemos ayudar hoy:"
            botones_bot = {
                "tipo": "lista", "boton": "Opciones Cosechas",
                "opciones": ["Menú y Precios", "Radicar PQRS", "Domicilios", "Hoja de Vida", "Franquicias Col", "Franquicias Ext"]
            }
        elif texto == "rechazar":
            estado_actual = "menu_principal"
            respuesta_bot = "Entendido. No podemos procesar solicitudes sin tu consentimiento sobre el tratamiento de datos. Si cambias de opinión, escribe 'Hola'."
        else:
            respuesta_bot = "⚠️ Opción no reconocida.\nPor favor, utiliza los botones debajo para confirmar si aceptas la Política de Tratamiento de Datos:"
            botones_bot = ["Aceptar", "Rechazar"]

    elif estado_actual == "menu_opciones":
        if "hola" in texto:
            respuesta_bot = "Menú Principal 🥤. Por favor, selecciona una opción de la lista:"
            botones_bot = {
                "tipo": "lista", "boton": "Opciones Cosechas",
                "opciones": ["Menú y Precios", "Radicar PQRS", "Domicilios", "Hoja de Vida", "Franquicias Col", "Franquicias Ext"]
            }
            
        elif texto == "menú y precios":
            estado_actual = "esperando_tipo_menu"
            respuesta_bot = (
                "¡Excelente elección! 🥤\n"
                "Para brindarte una mejor experiencia, contamos con nuestras cartas en Español e Inglés.\n\n"
                "Por favor, abre la lista y selecciona el menú que deseas consultar:"
            )
            botones_bot = {
                "tipo": "lista", "boton": "Ver Menús",
                "opciones": ["Nacional (ES)", "National (EN)", "Aeropuerto (ES)", "Airport (EN)"]
            }
            
        elif texto == "radicar pqrs":
            estado_actual = "esperando_nit"
            respuesta_bot = "Para direccionar tu queja, escribe el *NIT* de la factura (ej: 900111222). Si no tienes la factura a la mano, toca 'No tengo NIT'."
            botones_bot = ["No tengo NIT", "Volver"]
            
        elif texto == "domicilios":
            estado_actual = "esperando_ubicacion"
            respuesta_bot = (
                "¡Excelente! 🛵 Para mostrarte la sede con domicilios más cercana, "
                "por favor envíame tu ubicación actual.\n\n"
                "📱 *Si estás en celular:*\n"
                "Toca el ícono del clip 📎 (o el +) y selecciona 'Ubicación'.\n\n"
                "💻 *Si estás en computador (WhatsApp Web):*\n"
                "Como no es posible enviar la ubicación desde el PC, toca el botón de abajo para ver nuestro directorio completo."
            )
            botones_bot = ["Directorio Web", "Volver"]

        elif texto == "hoja de vida":
            respuesta_bot = (
                "¡Gracias por escribirnos!\nNos encanta saber que somos una alternativa al momento de buscar empleo, para ello ten cuenta los siguientes puntos:\n\n"
                "1. *Para ser parte de nuestra familia Cosechas en uno de nuestros puntos de venta como asesor:*\n"
                "Debes acercarte directamente a la tienda y entregar allí tu hoja de vida, ya que son los franquiciados (dueños del punto de venta) quienes realizan esta contratación de forma directa.\n\n"
                "2. *Para ser parte de nuestra familia Cosechas en el área Operaria o administrativa de la Franquicia Máster:*\n"
                "Envíanos tu hoja de vida al correo de Talento Humano:\nanalistaseleccionbebidas@cerealesselecta.com\n\n"
                "Ellos se encargarán de comunicarse contigo en caso de cumplir con el perfil de alguna de nuestras vacantes vigentes.\n\n"
                "¡Feliz día! 🌱😉🌱"
            )
            botones_bot = ["Volver", "Finalizar"]

        elif texto == "franquicias col" or texto == "franquicias colombia":
            estado_actual = "esperando_interes_franquicia"
            documento_bot = {
                "url": "https://wfvjzahmxzzjtyimkfcr.supabase.co/storage/v1/object/public/franquicias_colombia/PRESENTACION%20FRANQUICIAS%202026_v3.pdf", 
                "nombre": "Portafolio_Franquicias_Cosechas.pdf"
            }
            respuesta_bot = (
                "¡Qué gran noticia que desees emprender y unirte a la familia Cosechas! 🌱\n\n"
                "Te hemos adjuntado nuestro portafolio oficial. Revísalo y cuéntanos:\n"
                "¿Deseas continuar con el proceso de solicitud?"
            )
            botones_bot = ["Sí, me interesa", "No por ahora"]

        elif texto == "franquicias ext" or texto == "franquicias exterior" or texto == "franquicias otros paises":
            respuesta_bot = (
                "¡Hola! Gracias por escribirnos y por tu gran interés en expandir la familia Cosechas a nuevos horizontes. 🌍\n\n"
                "Para conocer todos los detalles sobre nuestro modelo internacional y contactar directamente a nuestro equipo de casa matriz, te invitamos a visitar nuestra página web oficial:\n\n"
                "👉 *www.cosechas.com*\n\n"
                "¡Mucho éxito con tu proyecto! ¿Deseas consultar algo más? 🌱"
            )
            botones_bot = ["Volver", "Finalizar"]

        else:
            respuesta_bot = "⚠️ No logré entender eso. Por favor, selecciona una de las siguientes opciones desde el botón:"
            botones_bot = {
                "tipo": "lista", "boton": "Ver Opciones",
                "opciones": ["Menú y Precios", "Radicar PQRS", "Domicilios", "Hoja de Vida", "Franquicias Col", "Franquicias Ext"]
            }

    elif estado_actual == "esperando_ubicacion":
        if texto == "directorio web":
            estado_actual = "menu_opciones"
            respuesta_bot = (
                "🗺️ ¡Claro que sí! Puedes buscar la sede más cercana a tu ubicación en nuestro directorio web oficial:\n"
                "👉 https://www.cosechasexpress.com/encuentranos/\n\n"
                "¿Deseas consultar algo más?"
            )
            botones_bot = ["Volver", "Finalizar"]
            
        elif "[ubicacion]:" in texto:
            try:
                coordenadas = texto.split("]:")[1].split(",")
                lat = float(coordenadas[0])
                lon = float(coordenadas[1])
                
                sede = encontrar_sede_mas_cercana(lat, lon)
                
                if sede:
                    try:
                        supabase.table("registros_domicilios").insert({
                            "nombre_sede": sede['nombre']
                        }).execute()
                    except Exception as e:
                        print(f"Error guardando analítica de domicilio: {e}")

                    maps_url = f"https://www.google.com/maps/search/?api=1&query={sede['latitud']},{sede['longitud']}"
                    respuesta_bot = (
                        f"📍 *Sede Cosechas más cercana encontrada:*\n\n"
                        f"🏪 *{sede['nombre']}*\n"
                        f"📏 A tan solo *{sede['distancia_km']} km* de tu ubicación.\n"
                        f"📞 Teléfono Domicilios: {sede['telefono']}\n"
                        f"🗺️ Dirección: {sede['direccion']}\n\n"
                        f"👉 *¿Cómo llegar?* Toca el enlace para abrir el mapa:\n{maps_url}\n\n"
                        "¿Deseas consultar algo más?"
                    )
                else:
                    respuesta_bot = "Lo siento, en este momento no tenemos sedes registradas en nuestro sistema. 😔\n¿Deseas consultar algo más?"
                    
                estado_actual = "menu_opciones"
                botones_bot = ["Volver", "Finalizar"]
                
            except Exception as e:
                print(f"Error procesando ubicación: {e}")
                respuesta_bot = "Hubo un error calculando la distancia. Intenta nuevamente o toca 'Volver'."
                botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ No detecté una ubicación válida.\n\nPor favor, usa el ícono del clip 📎 para compartir tu 'Ubicación actual', o toca 'Directorio Web' si estás en computador."
            botones_bot = ["Directorio Web", "Volver"]

    elif estado_actual == "esperando_tipo_menu":
        if texto == "nacional (es)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": "https://wfvjzahmxzzjtyimkfcr.supabase.co/storage/v1/object/public/cartas-cosechas/MENU%20DIGITAL.pdf",
                "nombre": "Carta_Nacional_ES_Cosechas.pdf"
            }
            respuesta_bot = "📄 Aquí tienes nuestra carta Nacional en Español.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Volver", "Finalizar"]

        elif texto == "national (en)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": "https://wfvjzahmxzzjtyimkfcr.supabase.co/storage/v1/object/public/cartas-cosechas/MENU%20DIGITAL%20INGLES.pdf",
                "nombre": "National_Menu_EN_Cosechas.pdf"
            }
            respuesta_bot = "📄 Here is our National Menu in English.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Volver", "Finalizar"]

        elif texto == "aeropuerto (es)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": "https://wfvjzahmxzzjtyimkfcr.supabase.co/storage/v1/object/public/cartas-cosechas/MENU%20DIGITAL%20Aeropuerto.pdf",
                "nombre": "Carta_Aeropuertos_ES_Cosechas.pdf"
            }
            respuesta_bot = "📄 Aquí tienes nuestra carta para Aeropuertos en Español.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Volver", "Finalizar"]

        elif texto == "airport (en)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": "https://wfvjzahmxzzjtyimkfcr.supabase.co/storage/v1/object/public/cartas-cosechas/MENU%20DIGITAL%20Aeropuerto%20INGLES.pdf",
                "nombre": "Airports_Menu_EN_Cosechas.pdf"
            }
            respuesta_bot = "📄 Here is our Airport Menu in English.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Volver", "Finalizar"]

        else:
            respuesta_bot = "⚠️ Opción inválida. Por favor, abre la lista y selecciona uno de los menús disponibles:"
            botones_bot = {
                "tipo": "lista", "boton": "Ver Menús",
                "opciones": ["Nacional (ES)", "National (EN)", "Aeropuerto (ES)", "Airport (EN)"]
            }

    # --- FLUJO DE PQRS BLINDADO ---
    elif estado_actual == "esperando_nit":
        if texto == "no tengo nit":
            estado_actual = "esperando_barrio_pqrs"
            respuesta_bot = "No te preocupes. Por favor, escríbeme en qué *ciudad y barrio* o zona se encuentra la tienda (ejemplo: 'Medellín Laureles' o 'Bogotá Chapinero'):"
            botones_bot = ["Sedes Generales", "Volver"]
        else:
            # --- NUEVO: INTERCEPTOR Y NORMALIZADOR DE NIT ---
            import re
            
            # 1. Extraemos solo los números de lo que escribió el cliente
            solo_numeros = re.sub(r'\D', '', texto)
            
            # 2. Le aplicamos el mismo formato con puntos del Frontend (Ej: 900111222 -> 900.111.222)
            nit_formateado = texto # Por si acaso escribió letras, lo dejamos igual por defecto
            if solo_numeros:
                nit_formateado = "{:,}".format(int(solo_numeros)).replace(',', '.')
                
            # 3. Buscamos en Supabase de forma TRIPLE usando un "OR"
            # Buscará: El texto crudo OR el texto con puntos OR el texto solo números
            filtro_triple = f"tercero_nit.eq.{texto},tercero_nit.eq.{nit_formateado},tercero_nit.eq.{solo_numeros}"
            
            respuesta_db = supabase.table("sedes_oficiales").select("*").or_(filtro_triple).execute()
            # ------------------------------------------------
            
            if len(respuesta_db.data) > 0:
                franquicia = respuesta_db.data[0]
                datos_pqrs["nit"] = franquicia["tercero_nit"]
                datos_pqrs["local"] = franquicia["ceco_nombre"]
                datos_pqrs["correo_franquiciado"] = franquicia.get("admin_correo") or EMAIL_USER 
                
                estado_actual = "esperando_tipo_reporte"
                respuesta_bot = f"✅ Sede identificada: {franquicia['ceco_nombre']}.\n\n¿Qué tipo de reporte deseas realizar?"
                botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]
            else:
                respuesta_bot = "⚠️ El NIT o número ingresado no existe en nuestra base de datos. Por favor, revísalo y escríbelo de nuevo, o toca el botón para buscar por barrio:"
                botones_bot = ["No tengo NIT", "Volver"]

    elif estado_actual == "esperando_barrio_pqrs":
        if texto == "sedes generales":
            datos_pqrs["nit"] = None 
            datos_pqrs["correo_franquiciado"] = EMAIL_USER
            datos_pqrs["local"] = "Sedes Generales"
            estado_actual = "esperando_tipo_reporte"
            respuesta_bot = "Entendido. Radicaremos el reporte a nivel general.\n\n¿Qué tipo de reporte deseas realizar?"
            botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]
        else:
            try:
                res = supabase.rpc("buscar_sede_cercana", {"busqueda": texto}).execute()
                tiendas = res.data
            except Exception as e:
                print("Error RPC Supabase:", e)
                tiendas = []

            if tiendas:
                estado_actual = "seleccionando_sede_pqrs"
                opciones_lista = []
                for t in tiendas:
                    # Garantizar compatibilidad sin importar cómo se llamen las columnas de retorno
                    nombre_db = t.get("nombre_sede") or t.get("ceco_nombre") or "Sede Cosechas"
                    ciudad_db = t.get("ciudad") or t.get("pdv_ciudad") or ""
                    dir_db = t.get("direccion") or t.get("pdv_direccion") or ""
                    nit_db = t.get("nit") or t.get("tercero_nit") or "SIN_NIT"
                    
                    nombre = str(nombre_db)[:24]
                    desc = f"{ciudad_db} - {dir_db}"[:72]
                    
                    opciones_lista.append({
                        "id": f"nit_{nit_db}",
                        "title": nombre,
                        "description": desc
                    })
                
                respuesta_bot = f"Encontramos estas opciones cercanas a '{texto_usuario}'. Despliega el menú y selecciona la sede correcta:"
                botones_bot = {
                    "tipo": "lista", 
                    "boton": "Ver Tiendas",
                    "opciones": opciones_lista
                }
            else:
                respuesta_bot = "No encontré tiendas con esa ubicación. ¿Puedes intentar con otro barrio o ciudad? (O toca 'Sedes Generales')."
                botones_bot = ["Sedes Generales", "Volver"]

    elif estado_actual == "seleccionando_sede_pqrs":
        nit_seleccionado = None
        if texto.startswith("nit_"):
            nit_seleccionado = texto.replace("nit_", "")
        else:
            res_db = supabase.table("sedes_oficiales").select("tercero_nit").ilike("ceco_nombre", f"%{texto}%").execute()
            if res_db.data:
                nit_seleccionado = res_db.data[0]["tercero_nit"]

        if nit_seleccionado and nit_seleccionado != "sin_nit":
            res_fr = supabase.table("sedes_oficiales").select("*").eq("tercero_nit", nit_seleccionado).execute()
            if res_fr.data:
                franquicia = res_fr.data[0]
                datos_pqrs["nit"] = franquicia["tercero_nit"]
                datos_pqrs["local"] = franquicia["ceco_nombre"]
                datos_pqrs["correo_franquiciado"] = franquicia.get("admin_correo") or EMAIL_USER
                
                estado_actual = "esperando_tipo_reporte"
                respuesta_bot = f"✅ Sede confirmada: {franquicia['ceco_nombre']}.\n\n¿Qué tipo de reporte deseas realizar?"
                botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]
            else:
                estado_actual = "esperando_barrio_pqrs"
                respuesta_bot = "Error al confirmar la sede. Intenta escribir el barrio de nuevo:"
                botones_bot = ["Sedes Generales", "Volver"]
        else:
            datos_pqrs["nit"] = None
            datos_pqrs["local"] = texto_usuario.title() 
            datos_pqrs["correo_franquiciado"] = EMAIL_USER
            estado_actual = "esperando_tipo_reporte"
            respuesta_bot = f"✅ Sede registrada.\n\n¿Qué tipo de reporte deseas realizar?"
            botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]

    elif estado_actual == "esperando_tipo_reporte":
        if texto in ["inconformidad", "sugerencia", "felicitación", "felicitacion"]:
            datos_pqrs["tipo_reporte"] = texto.capitalize()
            if texto in ["felicitación", "felicitacion"]:
                estado_actual = "esperando_detalle_pqrs"
                respuesta_bot = "¡Qué alegría! Nos motiva mucho leer esto. Por favor, *escribe en un solo mensaje* tu felicitación:\n\n*(Si deseas cancelar, toca 'Volver')*"
                botones_bot = ["Volver"]
            else:
                estado_actual = "esperando_motivo_pqrs"
                respuesta_bot = "Entendido. ¿Cuál es el motivo principal de tu reporte?"
                botones_bot = ["Servicio", "Producto", "Servicio-Producto"]
        else:
            respuesta_bot = "⚠️ Opción no reconocida. Por favor, elige una opción:"
            botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]

    elif estado_actual == "esperando_motivo_pqrs":
        if texto in ["servicio", "producto", "servicio-producto"]:
            motivo_seleccionado = "Servicio-Producto" if texto == "servicio-producto" else texto.capitalize()
            datos_pqrs["motivo"] = motivo_seleccionado
            estado_actual = "esperando_novedad_pqrs"
            
            if texto == "servicio":
                respuesta_bot = "Selecciona el tipo de novedad respecto al *Servicio*:"
                botones_bot = {
                    "tipo": "lista", "boton": "Ver Novedades",
                    "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Pago/Novedad", "Disponibilidad carta"]
                }
            elif texto == "producto":
                respuesta_bot = "Selecciona el tipo de novedad respecto al *Producto*:"
                botones_bot = {
                    "tipo": "lista", "boton": "Ver Novedades",
                    "opciones": ["Preparación", "Objeto en el producto", "Presentación producto"]
                }
            else:
                respuesta_bot = "Selecciona el tipo de novedad de *Servicio o Producto* que más se ajuste:"
                botones_bot = {
                    "tipo": "lista", "boton": "Ver Novedades",
                    "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Pago/Novedad", "Disponibilidad carta", "Preparación", "Objeto en el producto", "Presentación producto"]
                }
        else:
            respuesta_bot = "⚠️ Opción no reconocida. Por favor, elige el motivo:"
            botones_bot = ["Servicio", "Producto", "Servicio-Producto"]

    elif estado_actual == "esperando_novedad_pqrs":
        opciones_validas = [
            "actitud del asesor", "horario", "presentación sede", "presentacion sede", 
            "pago/novedad", "disponibilidad carta", "preparación", "preparacion", "objeto en el producto", "presentación producto", "presentacion producto"
        ]
        if texto in opciones_validas:
            # Revertir la normalización de la tilde al capitalizar
            novedad_text = texto_usuario
            if texto in ["presentacion sede", "presentación sede"]: novedad_text = "Presentación establecimiento"
            if texto == "preparacion": novedad_text = "Preparación"
            if texto in ["presentacion producto", "presentación producto"]: novedad_text = "Presentación del producto"
            
            datos_pqrs["tipo"] = novedad_text.capitalize() if novedad_text not in ["Presentación establecimiento", "Presentación del producto"] else novedad_text
            estado_actual = "esperando_detalle_pqrs"
            respuesta_bot = "Entendido. Por favor, *escribe en un solo mensaje* el detalle exacto de lo sucedido:\n\n*(Si deseas cancelar, toca 'Volver')*"
            botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ Novedad no reconocida. Por favor selecciona una opción de la lista:"
            mot = datos_pqrs.get("motivo", "").lower()
            if mot == "servicio":
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Pago/Novedad", "Disponibilidad carta"]}
            elif mot == "producto":
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Preparación", "Objeto en el producto", "Presentación producto"]}
            else:
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Pago/Novedad", "Disponibilidad carta", "Preparación", "Objeto en el producto", "Presentación producto"]}

    elif estado_actual == "esperando_detalle_pqrs":
        datos_pqrs["detalle"] = texto_usuario 
        estado_actual = "esperando_evidencia_pqrs"
        respuesta_bot = "Detalle guardado. ¿Tienes alguna foto que desees adjuntar?\n(📸 *Envía la foto* ahora mismo o interactúa con los botones)."
        botones_bot = ["Saltar Foto", "Volver"]

    elif estado_actual == "esperando_evidencia_pqrs":
        if texto == "saltar foto":
            tiene_foto = "Sin evidencia"
        elif "[imagen_url]:" in texto:
            tiene_foto = texto.split("]:")[1]
        else:
            return "⚠️ No detecté una imagen válida.\n\nPor favor, envía la fotografía real, o utiliza las opciones en pantalla:", ["Saltar Foto", "Volver"], None

        correo_f = datos_pqrs.get("correo_franquiciado", EMAIL_USER)
        tipo = datos_pqrs.get("tipo", "No especificado")
        tipo_reporte = datos_pqrs.get("tipo_reporte", "Novedad")
        motivo = datos_pqrs.get("motivo", None)
        
        detalle = datos_pqrs.get("detalle", "")
        nit_guardar = datos_pqrs.get("nit")
        local_nombre = datos_pqrs.get("local", "Cosechas")
        
        destinatario_interno = EMAIL_COORD_SAC
        nombre_area = "Coordinación de Servicio al Cliente"
        correos_extra = []

        if tipo_reporte in ["Inconformidad", "Sugerencia"]:
            if motivo in ["Servicio", "Servicio-Producto"]:
                destinatario_interno = EMAIL_COORD_SAC
                nombre_area = "Coordinación de Servicio al Cliente"
                if tipo == "Pago/Novedad":
                    correos_extra.append(EMAIL_SISTEMAS)
            elif motivo == "Producto":
                if tipo in ["Preparación", "Presentación del producto"]:
                    destinatario_interno = EMAIL_CAPACITADORA
                    nombre_area = "Capacitación"
                elif tipo == "Objeto en el producto":
                    destinatario_interno = EMAIL_GERENCIA_JURIDICA
                    nombre_area = "Gerencia Jurídica y Servicio al Cliente"
                    correos_extra.append(EMAIL_COORD_SAC)

        # Armar las listas separadas
        correo_franquiciado_str = correo_f
        correos_internos = [c for c in [destinatario_interno, EMAIL_JEFE] + correos_extra if c]
        correos_internos_str = ", ".join(correos_internos)
        
        numero_radicado = "PENDIENTE"

        # --- SEPARACIÓN TÉCNICA 1: Inserción en DB ---
        try:
            respuesta_insert = supabase.table("tickets_pqrs").insert({
                "celular_cliente": celular, "nit_franquiciado": nit_guardar, "nombre_franquicia": local_nombre,
                "tipo_reporte": tipo_reporte, "motivo": motivo,
                "tipo_novedad": tipo, "detalle": detalle, "evidencia": tiene_foto 
            }).execute()
            
            if respuesta_insert.data:
                numero_radicado = str(respuesta_insert.data[0]['id'])
        except Exception as e:
            print(f"❌ Error en DB (Posible Foreign Key): {e}")

        # --- SEPARACIÓN TÉCNICA 2: Envío de Correos Independientes ---
        try:
            tipo_completo = f"{tipo_reporte} ({motivo}) - {tipo}" if motivo else f"{tipo_reporte} - {tipo}"
            
            # 1. Al Franquiciado
            enviar_correo_pqrs_franquiciado(correo_franquiciado_str, numero_radicado, tipo_completo, detalle, local_nombre, celular, destinatario_interno, nombre_area)
            
            # 2. Al Equipo Interno
            if correos_internos_str:
                enviar_correo_pqrs_interno(correos_internos_str, numero_radicado, tipo_completo, detalle, local_nombre, celular, nombre_area)
                
            print("✅ Correos PQRS enviados separadamente.")
        except Exception as e:
            print(f"❌ Error al enviar correos PQRS: {e}")

        estado_actual = "menu_opciones"
        datos_pqrs = {}
        
        if numero_radicado == "PENDIENTE":
            respuesta_bot = "✅ *PQRS Recibida*\n\nTu solicitud ha sido enviada al área correspondiente. (Experimentamos un leve retraso en nuestro sistema para generar tu número de radicado, pero tu novedad fue registrada)."
        else:
            respuesta_bot = f"✅ *PQRS Radicada Exitosamente*\n*Ticket: #{numero_radicado}*\n\nTu solicitud ha sido enviada al área correspondiente."
            
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_interes_franquicia":
        if texto in ["sí, me interesa", "si, me interesa", "si"]:
            estado_actual = "esperando_ciudad_franquicia" 
            respuesta_bot = "¡Excelente! 🎉 Para empezar, por favor dime:\n\n📍 *¿En qué ciudad te gustaría abrir tu franquicia Cosechas?*"
            botones_bot = ["Volver"]
        elif texto in ["no por ahora", "no"]:
            estado_actual = "menu_opciones"
            respuesta_bot = "Entendemos. Estaremos aquí cuando decidas dar el gran paso. ¡Mucho éxito! 🥤\n\n¿Deseas consultar algo más?"
            botones_bot = ["Volver", "Finalizar"]
        else:
            respuesta_bot = "⚠️ Por favor, utiliza los botones para indicarnos si deseas continuar:"
            botones_bot = ["Sí, me interesa", "No por ahora"]

    elif estado_actual == "esperando_ciudad_franquicia":
        datos_pqrs["ciudad_franquicia"] = texto_usuario 
        estado_actual = "esperando_direccion_local"
        respuesta_bot = (
            f"¡Perfecto! {texto_usuario.title()} es una excelente plaza para Cosechas. 🥤\n\n"
            "Para avanzar, necesitamos evaluar la ubicación. Por favor, escríbeme la *dirección exacta del posible local* que tienes en vista.\n\n"
            "⚠️ *Nota:* Te recomendamos NO firmar contratos ni arrendar el local hasta que nuestro equipo de expansión apruebe la viabilidad del punto.\n\n"
            "*(Si aún no tienes una opción vista, toca el botón de abajo)*"
        )
        botones_bot = ["Aún no tengo local", "Volver"]

    elif estado_actual == "esperando_direccion_local":
        if texto in ["aún no tengo local", "aun no tengo local"]:
            estado_actual = "menu_opciones"
            respuesta_bot = (
                "Entendemos. Para poder realizar el estudio de viabilidad y avanzar con tu solicitud, es requisito indispensable tener al menos una opción de local comercial en vista para ser evaluada.\n\n"
                "¡Te invitamos a buscar el lugar ideal y escribirnos nuevamente cuando tengas un posible local! Estaremos felices de apoyarte a cumplir este sueño. 🌱"
            )
            botones_bot = ["Volver", "Finalizar"]
        else:
            datos_pqrs["direccion_local"] = texto_usuario 
            estado_actual = "esperando_dudas_franquicia"
            respuesta_bot = (
                "¡Perfecto! Hemos registrado la posible dirección para su evaluación.\n\n"
                "Ahora, por favor escríbeme *en un solo mensaje* qué dudas o inquietudes tienes sobre el modelo de negocio o el proceso a seguir:"
            )
            botones_bot = ["Volver"]

    elif estado_actual == "esperando_dudas_franquicia":
        dudas = texto_usuario
        direccion = datos_pqrs.get("direccion_local", "No especificada")
        ciudad = datos_pqrs.get("ciudad_franquicia", "No especificada") 
        
        try:
            supabase.table("solicitudes_franquicia").insert({
                "celular": celular, "ciudad": ciudad, "direccion_local": direccion, "dudas": dudas
            }).execute()
            enviar_correo_nueva_franquicia(celular, ciudad, direccion, dudas)
        except Exception as e:
            print("Error al guardar lead de franquicia:", e)

        estado_actual = "menu_opciones"
        datos_pqrs = {} 
        respuesta_bot = (
            "✅ *¡Solicitud enviada con éxito!*\n\n"
            "Hemos recibido tus datos y tus inquietudes. Un asesor de expansión se comunicará contigo próximamente al número con el que nos estás escribiendo para brindarte toda la asesoría.\n\n"
            "¡Gracias por querer crecer con Cosechas! 🥤"
        )
        botones_bot = ["Volver", "Finalizar"]

    # --- PASO C: SINCRONIZACIÓN DE ESTADO ---
    try:
        supabase.table("sesiones_bot").update({
            "estado": estado_actual, "datos_pqrs": datos_pqrs, "fecha_actualizacion": datetime.now(timezone.utc).isoformat()
        }).eq("celular", celular).execute()
    except Exception as e:
        print("Error al actualizar la sesión:", e)

    return respuesta_bot, botones_bot, documento_bot