from datetime import datetime, timezone
from config import supabase, SMTP_USER, R2_PUBLIC_URL
from services.email_service import enviar_correo_pqrs_franquiciado, enviar_correo_pqrs_interno, enviar_correo_nueva_franquicia, enviar_correo_hoja_vida
from services.location_service import analizar_ubicacion_sedes
from services.time_utils import parse_and_check_horario
import unicodedata

def normalizar_texto_busqueda(texto: str) -> list:
    if not texto: return []
    t = texto.lower().replace(',', ' ').replace('.', ' ')
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    reemplazos = {
        "calle": "cl", "carrera": "cr", "avenida": "av", "hospital": "hosp", 
        "centro comercial": "cc", "numero": "#", "nro": "#", "no": "#"
    }
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    palabras = t.split()
    relleno = {"con", "y", "de", "la", "el", "los", "las", "en", "un", "una"}
    return [p for p in palabras if p not in relleno and len(p) > 1]

def calcular_coincidencia(palabras_usuario, palabras_target):
    if not palabras_usuario: return 0
    # Búsqueda substring: permite que 'hosp' coincida con 'hospital' o 'cl' con 'cll' dentro del target
    coincidencias = 0
    for pu in palabras_usuario:
        if any(pu in pt for pt in palabras_target):
            coincidencias += 1
    return coincidencias / len(palabras_usuario)

def guardar_lead_franquicia(celular, datos):
    try:
        supabase.table("solicitudes_franquicia").insert({
            "celular": celular,
            "nombre": datos.get("nombre_franquicia", "No especificado"),
            "ciudad": datos.get("ciudad_franquicia", "No especificado"),
            "correo": datos.get("correo_franquicia", "No especificado"),
            "local_identificado": datos.get("local_identificado", "No"),
            "involucramiento": datos.get("involucramiento", "No"),
            "tipo_franquicia": datos.get("tipo_franquicia", ""),
            "direccion_local": datos.get("direccion_local", ""),
            "foto_local": datos.get("foto_local", "")
        }).execute()
        enviar_correo_nueva_franquicia(
            celular, 
            datos.get("ciudad_franquicia", ""), 
            datos.get("local_identificado", ""), 
            datos.get("involucramiento", ""), 
            datos.get("nombre_franquicia", ""), 
            datos.get("correo_franquicia", ""),
            datos.get("tipo_franquicia", ""),
            datos.get("direccion_local", ""),
            datos.get("foto_local", "")
        )
    except Exception as e:
        print("Error al guardar lead de franquicia:", e)

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
            "opciones": ["Menú y Precios", "Radicar PQRS", "Info de Domicilios", "Horarios", "Hoja de Vida", "Franquicias Col"]
        }, None

    despedidas = ["finalizar", "terminar", "cerrar", "chao", "adios", "hasta luego", "salir"]
    es_despedida = any(palabra in texto for palabra in despedidas) or "gracias" in texto

    if es_despedida:
        if estado_actual != "menu_principal":
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

    # Interceptar atajo de domicilio antes de la máquina de estados
    if estado_actual == "menu_opciones" and texto == "consultar domicilio" and "horario_sede_lat" in datos_pqrs:
        estado_actual = "esperando_ubicacion"
        texto = f"[atajo_domicilio]:{datos_pqrs['horario_sede_lat']},{datos_pqrs['horario_sede_lon']}"

    # --- PASO B: MÁQUINA DE ESTADOS LÓGICOS ---
    if estado_actual == "menu_principal":
        estado_actual = "esperando_terminos"
        respuesta_bot = (
            "¡Hola! Bienvenido al asistente virtual de Cosechas 🥤.\n\n"
            "Para garantizar la seguridad de tus datos, "
            "por favor conoce nuestra Política de Tratamiento de Datos aquí:\n"
            "👉 https://www.cosechasexpress.com/politica-de-tratamiento-de-datos/\n\n"
            "¿Aceptas la política para continuar?"
        )
        botones_bot = ["Aceptar", "Rechazar"]

    elif estado_actual == "esperando_terminos":
        if texto == "aceptar":
            estado_actual = "menu_opciones"
            respuesta_bot = "¡Perfecto! Gracias por confiar en nosotros. Por favor, despliega la lista y selecciona cómo te podemos ayudar hoy:"
            botones_bot = {
                "tipo": "lista", "boton": "Opciones Cosechas",
                "opciones": ["Menú y Precios", "Radicar PQRS", "Info de Domicilios", "Horarios", "Hoja de Vida", "Franquicias Col"]
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
                "opciones": ["Menú y Precios", "Radicar PQRS", "Info de Domicilios", "Horarios", "Hoja de Vida", "Franquicias Col"]
            }
            
        elif texto == "menú y precios":
            estado_actual = "esperando_tipo_menu"
            respuesta_bot = (
                "¡Excelente elección! 🥤\n"
                "Para brindarte una mejor experiencia, contamos con nuestras cartas en Español e Inglés.\n"
                "*(Recuerda que aeropuertos y otras poblaciones como Leticia cuentan con un precio diferente)*\n\n"
                "Por favor, abre la lista y selecciona el menú que deseas consultar:"
            )
            botones_bot = {
                "tipo": "lista", "boton": "Ver Menús",
                "opciones": ["Nacional (ES)", "National (EN)", "Aeropuertos/Leticia", "Airports/Others EN"]
            }
            
        elif texto == "radicar pqrs":
            estado_actual = "esperando_barrio_pqrs"
            respuesta_bot = "Para direccionar tu queja, escribe la *Ciudad y Barrio* donde ocurrió el suceso:"
            botones_bot = ["Sedes Generales", "Volver"]
            
        elif texto in ["domicilios", "info de domicilios", "información de domicilios", "informacion de domicilios"]:
            estado_actual = "esperando_ubicacion"
            respuesta_bot = (
                "¡Excelente! 🛵 Nosotros no hacemos o no nos encargamos del domicilio, sino que te damos la información de domicilio de la tienda más cercana.\n\n"
                "Para mostrarte la sede, por favor envíame tu ubicación actual.\n\n"
                "📱 *Si estás en celular:*\n"
                "Toca el ícono del clip 📎 (o el +) y selecciona 'Ubicación'.\n\n"
                "💻 *Si no puedes enviarla o estás en computador:*\n"
                "Escribe tu dirección exacta y ciudad (ejemplo: 'Calle 10 # 5-20, Bogotá')."
            )
            botones_bot = ["Volver"]

        elif texto == "hoja de vida":
            estado_actual = "esperando_area_trabajo"
            respuesta_bot = "¿Dónde te gustaría trabajar? Selecciona el área de tu interés:"
            botones_bot = ["Punto de Venta", "Planta Cosechas"]

        elif texto == "horarios":
            estado_actual = "esperando_barrio_horario"
            respuesta_bot = "Para indicarte el horario de atención, por favor escríbeme en qué *ciudad y barrio* se encuentra la tienda (ejemplo: 'Medellín Laureles' o 'Bogotá Chapinero'):"
            botones_bot = ["Volver"]

        elif texto == "franquicias col" or texto == "franquicias colombia":
            estado_actual = "esperando_nombre_franquicia"
            respuesta_bot = (
                "Hola 👋 gracias por tu interés en la franquicia de Cosechas 🍓\n\n"
                "Para brindarte una mejor asesoría y conocer más sobre tu perfil, queremos hacerte unas preguntas rápidas 😊 (esta info debe ser obligatoria para avanzar).\n\n"
                "Por favor, envíame tu *Nombre completo*:"
            )
            botones_bot = ["Volver"]

        else:
            respuesta_bot = "⚠️ No logré entender eso. Por favor, selecciona una de las siguientes opciones desde el botón:"
            botones_bot = {
                "tipo": "lista", "boton": "Ver Opciones",
                "opciones": ["Menú y Precios", "Radicar PQRS", "Info de Domicilios", "Horarios", "Hoja de Vida", "Franquicias Col"]
            }

    elif estado_actual == "esperando_ubicacion":
        lat_cliente = None
        lon_cliente = None
        is_atajo = False
        respuesta_bot = None
        
        if "[ubicacion]:" in texto or "[atajo_domicilio]:" in texto:
            is_atajo = "[atajo_domicilio]:" in texto
            try:
                coordenadas = texto.split("]:")[1].split(",")
                lat_cliente = float(coordenadas[0])
                lon_cliente = float(coordenadas[1])
            except:
                pass
        elif len(texto) > 5 and texto not in ["volver", "menú principal", "finalizar"]:
            # Validamos si la dirección tiene ciudad para evitar errores geográficos (incluyendo tiendas cerradas temporalmente)
            try:
                res = supabase.table("sedes_oficiales").select("pdv_ciudad").execute()
                ciudades = {s['pdv_ciudad'].lower() for s in res.data if s.get('pdv_ciudad')}
            except:
                ciudades = {"bogota", "medellin", "cali", "cartagena", "barranquilla"}
            
            import unicodedata
            txt_clean = ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')
            ciudades_clean = {''.join(c for c in unicodedata.normalize('NFD', ciu) if unicodedata.category(c) != 'Mn') for ciu in ciudades}
            
            tiene_ciudad = any(c in txt_clean for c in ciudades_clean)
            if not tiene_ciudad:
                estado_actual = "esperando_ubicacion"
                respuesta_bot = "⚠️ Para ubicarte con precisión, por favor asegúrate de incluir el nombre de tu ciudad en el mensaje (Ejemplo: Calle 10 # 5-20, Bogotá)."
                botones_bot = ["Volver"]
                
            else:
                from services.location_service import geocode_address
                lat_cliente, lon_cliente = geocode_address(texto)
                if not lat_cliente:
                    estado_actual = "esperando_ubicacion"
                    respuesta_bot = "❌ No pudimos encontrar esa dirección en el mapa. Por favor verifica que esté escrita correctamente junto con tu ciudad (Ejemplo: Calle 10 # 5-20, Bogotá)."
                    botones_bot = ["Volver"]
            
        if lat_cliente and lon_cliente:
            try:
                sede_absoluta, sede_dom = analizar_ubicacion_sedes(lat_cliente, lon_cliente, 10.0)
                
                if sede_absoluta:
                    try:
                        supabase.table("registros_domicilios").insert({
                            "nombre_sede": sede_absoluta.get('ceco_nombre', 'Sede Cosechas')
                        }).execute()
                    except Exception as e:
                        pass
                        
                    def format_opciones(s):
                        cel = s.get('pdv_celular')
                        rapp = str(s.get('pdv_aplicacion_rappi', '')).strip().title()
                        
                        tiene_propio = cel and str(cel).lower() != 'no'
                        tiene_app = rapp in ['Rappi', 'Didi', 'Ambos']
                        
                        if tiene_propio:
                            if tiene_app:
                                nombres_plat = "las plataformas Rappi y Didi" if rapp == 'Ambos' else f"la plataforma {rapp}"
                                return f"  🛵 Esta sede cuenta con domicilio propio, puedes pedir al número: {cel}.\n  📱 Adicionalmente, puedes encontrarla en {nombres_plat}."
                            else:
                                return f"  🛵 Esta sede cuenta con domicilio propio, puedes pedir al número: {cel}."
                        elif tiene_app:
                            nombres_plat = "las plataformas Rappi y Didi" if rapp == 'Ambos' else f"la plataforma {rapp}"
                            return f"  ⚠️ Esta sede no cuenta con domicilio propio, pero puedes pedir a través de {nombres_plat}."
                            
                        return ""
                        
                    maps_url_abs = f"https://www.google.com/maps/search/?api=1&query={sede_absoluta['latitud']},{sede_absoluta['longitud']}"
                    
                    opciones_abs = format_opciones(sede_absoluta)
                    
                    if opciones_abs:
                        estado_horario = parse_and_check_horario(sede_absoluta.get('pdv_horario', ''))
                        msg_abierto = "" if estado_horario["abierto_ahora"] else f"⚠️ *Atención: La sede se encuentra cerrada en este momento.*\n"
                        msg_horario = f"⏳ *Horario:* {estado_horario['mensaje_amigable']}\n\n"

                        if is_atajo:
                            respuesta_bot = (
                                f"🛵 *Opciones de domicilio para {sede_absoluta.get('ceco_nombre', 'esta sede')}*\n\n"
                                f"{msg_abierto}"
                                f"🗺️ Dirección: {sede_absoluta.get('pdv_direccion', 'No disponible')}\n"
                                f"{msg_horario}"
                                f"🛵 *Opciones de envío:*\n{opciones_abs}\n\n"
                                "¿Deseas consultar algo más?"
                            )
                        else:
                            respuesta_bot = (
                                f"🛵 *Sede Cosechas más cercana encontrada:*\n\n"
                                f"📍 *{sede_absoluta.get('ceco_nombre', 'Sede Cosechas')}*\n"
                                f"{msg_abierto}"
                                f"📏 A tan solo *{sede_absoluta['distancia_km']} km* de tu ubicación.\n"
                                f"🗺️ Dirección: {sede_absoluta.get('pdv_direccion', 'No disponible')}\n"
                                f"{msg_horario}"
                                f"🛵 *Opciones de envío:*\n{opciones_abs}\n\n"
                                f"🧭 *¿Cómo llegar?* Toca el enlace para abrir el mapa:\n{maps_url_abs}\n\n"
                                "¿Deseas consultar algo más?"
                            )
                    else:
                        if sede_dom and sede_dom['ceco_nombre'] != sede_absoluta['ceco_nombre']:
                            maps_url_dom = f"https://www.google.com/maps/search/?api=1&query={sede_dom['latitud']},{sede_dom['longitud']}"
                            opciones_dom = format_opciones(sede_dom)
                            
                            estado_horario_dom = parse_and_check_horario(sede_dom.get('pdv_horario', ''))
                            msg_abierto_dom = "" if estado_horario_dom["abierto_ahora"] else f"⚠️ *Atención: La sede se encuentra cerrada en este momento.*\n"
                            msg_horario_dom = f"⏳ *Horario:* {estado_horario_dom['mensaje_amigable']}\n\n"
                            
                            if is_atajo:
                                respuesta_bot = (
                                    f"⚠️ La sede *{sede_absoluta.get('ceco_nombre', 'Sede Cosechas')}* no cuenta con servicio a domicilio.\n\n"
                                    f"✅ *La sede con domicilio más cercana a esta es:*\n"
                                    f"📍 *{sede_dom.get('ceco_nombre', 'Sede Cosechas')}*\n"
                                    f"{msg_abierto_dom}"
                                    f"📏 A *{sede_dom['distancia_km']} km* de distancia.\n"
                                    f"🗺️ Dirección: {sede_dom.get('pdv_direccion', 'No disponible')}\n"
                                    f"{msg_horario_dom}"
                                    f"🛵 *Opciones de envío:*\n{opciones_dom}\n\n"
                                    f"🧭 *Ubicación Sede con Domicilio:*\n{maps_url_dom}\n\n"
                                    "¿Deseas consultar algo más?"
                                )
                            else:
                                respuesta_bot = (
                                    f"🛵 *Sede Cosechas más cercana:*\n"
                                    f"📍 *{sede_absoluta.get('ceco_nombre', 'Sede Cosechas')}* (a {sede_absoluta['distancia_km']} km)\n"
                                    f"⚠️ Esta sede actualmente no cuenta con servicio a domicilio.\n\n"
                                    f"✅ *La sede con domicilio más cercana a ti es:*\n"
                                    f"📍 *{sede_dom.get('ceco_nombre', 'Sede Cosechas')}*\n"
                                    f"{msg_abierto_dom}"
                                    f"📏 A *{sede_dom['distancia_km']} km* de tu ubicación.\n"
                                    f"🗺️ Dirección: {sede_dom.get('pdv_direccion', 'No disponible')}\n"
                                    f"{msg_horario_dom}"
                                    f"🛵 *Opciones de envío:*\n{opciones_dom}\n\n"
                                    f"🧭 *Ubicación Sede con Domicilio:*\n{maps_url_dom}\n\n"
                                    "¿Deseas consultar algo más?"
                                )
                        else:
                            if is_atajo:
                                respuesta_bot = (
                                    f"⚠️ *Lo sentimos, la sede {sede_absoluta.get('ceco_nombre', 'Sede Cosechas')} no cuenta con opciones de domicilio, y no hay otra sede cercana que sí lo tenga.*\n\n"
                                    "¿Deseas consultar algo más?"
                                )
                            else:
                                respuesta_bot = (
                                    f"🛵 *Sede Cosechas más cercana:*\n\n"
                                    f"📍 *{sede_absoluta.get('ceco_nombre', 'Sede Cosechas')}*\n"
                                    f"📏 A *{sede_absoluta['distancia_km']} km* de tu ubicación.\n"
                                    f"🗺️ Dirección: {sede_absoluta.get('pdv_direccion', 'No disponible')}\n\n"
                                    f"⚠️ *Lo sentimos, no hemos encontrado opciones de domicilio para las sedes cercanas (menos de 10km).*\n\n"
                                    f"🧭 *Ubicación:*\n{maps_url_abs}\n\n"
                                    "¿Deseas consultar algo más?"
                                )
                else:
                    respuesta_bot = "Lo siento, en este momento no tenemos sedes registradas en nuestro sistema. 🛵\n¿Deseas consultar algo más?"

                estado_actual = "menu_opciones"
                botones_bot = ["Menú y Precios", "Menú Principal", "Finalizar"]
                
            except Exception as e:
                print(f"Error procesando ubicación: {e}")
                respuesta_bot = "Hubo un error calculando la distancia. Intenta nuevamente o toca 'Volver'."
                botones_bot = ["Volver"]
        elif not respuesta_bot:
            respuesta_bot = "⚠️ No detecté una ubicación válida.\n\nPor favor, usa el ícono del clip 📎 para compartir tu 'Ubicación actual', o si estás en computador escribe tu dirección exacta y ciudad (ejemplo: 'Calle 10 # 5-20, Bogotá')."
            botones_bot = ["Volver"]

    # --- FLUJO DE HORARIOS ---
    elif estado_actual == "esperando_barrio_horario":
        try:
            res = supabase.table("sedes_oficiales").select("*").eq('pdv_estado', 'OPERANDO').execute()
            todas = res.data
            palabras_user = normalizar_texto_busqueda(texto)
            tiendas = []
            for s in todas:
                target = f"{s.get('ceco_nombre','')} {s.get('pdv_ciudad','')} {s.get('pdv_barrio','')} {s.get('pdv_ubicacion','')} {s.get('pdv_direccion','')}"
                palabras_target = normalizar_texto_busqueda(target)
                score = calcular_coincidencia(palabras_user, palabras_target)
                if score >= 0.6:  # Al menos 60% de coincidencia
                    # Añadir score para ordenar después
                    s['_score'] = score
                    tiendas.append(s)
            # Ordenar por mejor coincidencia
            tiendas.sort(key=lambda x: x['_score'], reverse=True)
        except Exception as e:
            print("Error Búsqueda Supabase Horarios:", e)
            tiendas = []

        if tiendas:
            estado_actual = "seleccionando_sede_horario"
            opciones_lista = []
            for t in tiendas[:10]: 
                nombre_db = t.get("ceco_nombre") or "Sede Cosechas"
                ciudad_db = t.get("pdv_ciudad") or ""
                dir_db = t.get("pdv_direccion") or ""
                
                nombre = str(nombre_db)[:24]
                desc = f"{ciudad_db} - {dir_db}"[:72]
                
                opciones_lista.append({
                    "id": f"hor_{nombre_db}"[:200],
                    "title": nombre,
                    "description": desc
                })
            
            respuesta_bot = f"Encontramos estas opciones cercanas a '{texto_usuario}'. Despliega el menú y selecciona la sede para conocer su horario:"
            botones_bot = {
                "tipo": "lista", 
                "boton": "Ver Tiendas",
                "opciones": opciones_lista
            }
        else:
            respuesta_bot = "No encontré tiendas con esa ubicación. ¿Puedes intentar con otro barrio o ciudad?"
            botones_bot = ["Volver"]

    elif estado_actual == "seleccionando_sede_horario":
        if texto.startswith("hor_"):
            nombre_sede_seleccionada = texto.replace("hor_", "")
            res_db = supabase.table("sedes_oficiales").select("*").ilike("ceco_nombre", nombre_sede_seleccionada).execute()
            
            if res_db.data:
                sede = res_db.data[0]
                estado_horario = parse_and_check_horario(sede.get("pdv_horario", ""))
                msg_abierto = "✅ *¡Estamos abiertos ahora!*" if estado_horario["abierto_ahora"] else "⚠️ *Actualmente nos encontramos cerrados.*"
                
                lat = sede.get('latitud')
                lon = sede.get('longitud')
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" if lat and lon else ""
                map_str = f"📍 *Ubicación:* {maps_url}\n\n" if maps_url else ""
                
                respuesta_bot = (
                    f"🏪 *{sede.get('ceco_nombre', 'Sede Cosechas')}*\n\n"
                    f"{msg_abierto}\n\n"
                    f"⏳ *Horario de Atención:*\n{estado_horario['mensaje_amigable']}\n\n"
                    f"🗺️ *Dirección:* {sede.get('pdv_direccion', 'No especificada')}\n"
                    f"{map_str}"
                    "¿Deseas consultar algo más?"
                )
                estado_actual = "menu_opciones"
                botones_bot = ["Menú Principal", "Consultar Domicilio", "Finalizar"]
                if lat and lon:
                    datos_pqrs["horario_sede_lat"] = lat
                    datos_pqrs["horario_sede_lon"] = lon
            else:
                respuesta_bot = "No logré identificar la sede. Por favor, intenta de nuevo."
                botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ Por favor, selecciona una de las sedes de la lista:"
            botones_bot = ["Volver"]

    # --- FLUJO DE HOJAS DE VIDA ---
    elif estado_actual == "esperando_tipo_menu":
        if texto == "nacional (es)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": f"{R2_PUBLIC_URL}/cartas/MENU_DIGITAL_ES.pdf",
                "nombre": "Carta_Nacional_ES_Cosechas.pdf"
            }
            respuesta_bot = "📄 Aquí tienes nuestra carta Nacional en Español.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Domicilios", "Menú Principal", "Finalizar"]

        elif texto == "national (en)": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": f"{R2_PUBLIC_URL}/cartas/MENU_DIGITAL_EN.pdf",
                "nombre": "National_Menu_EN_Cosechas.pdf"
            }
            respuesta_bot = "📄 Here is our National Menu in English.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Domicilios", "Menú Principal", "Finalizar"]

        elif texto == "aeropuertos/leticia" or texto == "aeropuerto": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": f"{R2_PUBLIC_URL}/cartas/MENU_AEROPUERTOS_ES.pdf",
                "nombre": "Carta_Aeropuertos_ES_Cosechas.pdf"
            }
            respuesta_bot = "📄 Aquí tienes nuestra carta para Aeropuertos y Leticia en Español.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Domicilios", "Menú Principal", "Finalizar"]

        elif texto == "airports/others en": 
            estado_actual = "menu_opciones"
            documento_bot = {
                "url": f"{R2_PUBLIC_URL}/cartas/MENU_AEROPUERTOS_EN.pdf",
                "nombre": "Airports_Menu_EN_Cosechas.pdf"
            }
            respuesta_bot = "📄 Here is our Airport Menu in English.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Domicilios", "Menú Principal", "Finalizar"]

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
    elif estado_actual == "esperando_barrio_pqrs":
        if texto == "sedes generales":
            datos_pqrs["nit"] = None 
            datos_pqrs["correo_franquiciado"] = SMTP_USER
            datos_pqrs["local"] = "Sedes Generales"
            estado_actual = "esperando_tipo_reporte"
            respuesta_bot = "Entendido. Radicaremos el reporte a nivel general.\n\n¿Qué tipo de reporte deseas realizar?"
            botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]
        else:
            try:
                res = supabase.table("sedes_oficiales").select("*").eq('pdv_estado', 'OPERANDO').execute()
                todas = res.data
                palabras_user = normalizar_texto_busqueda(texto)
                tiendas = []
                for s in todas:
                    target = f"{s.get('ceco_nombre','')} {s.get('pdv_ciudad','')} {s.get('pdv_barrio','')} {s.get('pdv_ubicacion','')} {s.get('pdv_direccion','')}"
                    palabras_target = normalizar_texto_busqueda(target)
                    score = calcular_coincidencia(palabras_user, palabras_target)
                    if score >= 0.6:
                        s['_score'] = score
                        tiendas.append(s)
                tiendas.sort(key=lambda x: x['_score'], reverse=True)
            except Exception as e:
                print("Error Búsqueda Supabase PQRS:", e)
                tiendas = []

            if tiendas:
                estado_actual = "seleccionando_sede_pqrs"
                opciones_lista = []
                for t in tiendas[:10]: 
                    nombre_db = t.get("ceco_nombre") or "Sede Cosechas"
                    ciudad_db = t.get("pdv_ciudad") or ""
                    dir_db = t.get("pdv_direccion") or ""
                    
                    nombre = str(nombre_db)[:24]
                    desc = f"{ciudad_db} - {dir_db}"[:72]
                    
                    opciones_lista.append({
                        "id": f"tnd_{nombre_db}"[:200],
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
        nombre_sede_seleccionada = None
        
        if texto.startswith("tnd_"):
            nombre_sede_seleccionada = texto.replace("tnd_", "")
            
            res_db = supabase.table("sedes_oficiales").select("*").ilike("ceco_nombre", nombre_sede_seleccionada).execute()
            if res_db.data:
                franquicia = res_db.data[0]
                datos_pqrs["nit"] = franquicia.get("tercero_nit", "SIN_NIT")
                datos_pqrs["local"] = franquicia.get("ceco_nombre", "Sede Desconocida")
                datos_pqrs["correo_franquiciado"] = franquicia.get("admin_correo") or SMTP_USER
                
                estado_actual = "esperando_tipo_reporte"
                respuesta_bot = f"✅ Sede confirmada: {franquicia.get('ceco_nombre', '')}.\n\n¿Qué tipo de reporte deseas realizar?"
                botones_bot = ["Inconformidad", "Sugerencia", "Felicitación"]
            else:
                estado_actual = "esperando_barrio_pqrs"
                respuesta_bot = "Error al confirmar la sede. Intenta escribir el barrio de nuevo:"
                botones_bot = ["Sedes Generales", "Volver"]
        else:
            try:
                res = supabase.table("sedes_oficiales").select("*").eq('pdv_estado', 'OPERANDO').execute()
                todas = res.data
                palabras_user = normalizar_texto_busqueda(texto)
                tiendas = []
                for s in todas:
                    target = f"{s.get('ceco_nombre','')} {s.get('pdv_ciudad','')} {s.get('pdv_barrio','')} {s.get('pdv_ubicacion','')} {s.get('pdv_direccion','')}"
                    palabras_target = normalizar_texto_busqueda(target)
                    score = calcular_coincidencia(palabras_user, palabras_target)
                    if score >= 0.6:
                        s['_score'] = score
                        tiendas.append(s)
                tiendas.sort(key=lambda x: x['_score'], reverse=True)
            except Exception as e:
                tiendas = []
                
            if tiendas:
                opciones_lista = []
                for t in tiendas[:10]:
                    nombre_db = t.get("ceco_nombre") or "Sede Cosechas"
                    ciudad_db = t.get("pdv_ciudad") or ""
                    dir_db = t.get("pdv_direccion") or ""
                    
                    opciones_lista.append({
                        "id": f"tnd_{nombre_db}"[:200],
                        "title": str(nombre_db)[:24],
                        "description": f"{ciudad_db} - {dir_db}"[:72]
                    })
                
                respuesta_bot = f"Por favor, asegúrate de desplegar el menú y seleccionar la tienda correcta de esta lista:"
                botones_bot = {
                    "tipo": "lista", 
                    "boton": "Ver Tiendas",
                    "opciones": opciones_lista
                }
            else:
                respuesta_bot = "No encontré tiendas con esa ubicación. ¿Puedes intentar con otro barrio o ciudad? (O toca 'Sedes Generales')."
                botones_bot = ["Sedes Generales", "Volver"]

    elif estado_actual == "esperando_tipo_reporte":
        if texto in ["inconformidad", "sugerencia", "felicitación", "felicitacion"]:
            datos_pqrs["tipo_reporte"] = texto.capitalize()
            if texto in ["felicitación", "felicitacion"]:
                estado_actual = "esperando_nombre_pqrs"
                respuesta_bot = "¡Qué alegría! Nos motiva mucho leer esto. Para saber quién nos escribe, por favor indícanos tu *Nombre Completo*:\n\n*(Si deseas cancelar, toca 'Volver')*"
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
                    "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Factura electrónica", "Disponibilidad carta"]
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
                    "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Factura electrónica", "Disponibilidad carta", "Preparación", "Objeto en el producto", "Presentación producto"]
                }
        else:
            respuesta_bot = "⚠️ Opción no reconocida. Por favor, elige el motivo:"
            botones_bot = ["Servicio", "Producto", "Servicio-Producto"]

    elif estado_actual == "esperando_novedad_pqrs":
        opciones_validas = [
            "actitud del asesor", "horario", "presentación sede", "presentacion sede", 
            "factura electrónica", "factura electronica", "disponibilidad carta", "preparación", "preparacion", "objeto en el producto", "presentación producto", "presentacion producto"
        ]
        if texto in opciones_validas:
            # Flujo Excepcional: Factura Electrónica
            if texto in ["factura electrónica", "factura electronica"]:
                datos_pqrs["tipo"] = "Factura electrónica"
                estado_actual = "esperando_doc_factura"
                respuesta_bot = (
                    "Recuerda que la factura electrónica debe ser solicitada en el mismo mes de la compra.\n\n"
                    "Para avanzar, por favor escribe el *Documento de Identidad* (Cédula o NIT) de quien solicita la factura:"
                )
                botones_bot = ["Volver"]
            else:
                # Revertir la normalización de la tilde al capitalizar
                novedad_text = texto_usuario
                if texto in ["presentacion sede", "presentación sede"]: novedad_text = "Presentación establecimiento"
                if texto == "preparacion": novedad_text = "Preparación"
                if texto in ["presentacion producto", "presentación producto"]: novedad_text = "Presentación del producto"
                
                datos_pqrs["tipo"] = novedad_text.capitalize() if novedad_text not in ["Presentación establecimiento", "Presentación del producto"] else novedad_text
                estado_actual = "esperando_nombre_pqrs"
                respuesta_bot = "Entendido. Para brindarte una atención personalizada, por favor escríbeme tu *Nombre Completo*:\n\n*(Si deseas cancelar, toca 'Volver')*"
                botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ Novedad no reconocida. Por favor selecciona una opción de la lista:"
            mot = datos_pqrs.get("motivo", "").lower()
            if mot == "servicio":
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Factura electrónica", "Disponibilidad carta"]}
            elif mot == "producto":
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Preparación", "Objeto en el producto", "Presentación producto"]}
            else:
                botones_bot = {"tipo": "lista", "boton": "Ver Novedades", "opciones": ["Actitud del asesor", "Horario", "Presentación sede", "Factura electrónica", "Disponibilidad carta", "Preparación", "Objeto en el producto", "Presentación producto"]}

    elif estado_actual == "esperando_doc_factura":
        datos_pqrs["documento_factura"] = texto_usuario
        estado_actual = "esperando_correo_factura"
        respuesta_bot = "Entendido. Ahora por favor escríbeme el *Correo Electrónico* donde deseas recibir la factura (obligatorio):"
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_correo_factura":
        datos_pqrs["correo_cliente"] = texto_usuario
        estado_actual = "esperando_nombre_factura"
        respuesta_bot = "Gracias. Por favor escríbeme el *Nombre Completo* o *Razón Social* para la factura:"
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_nombre_factura":
        datos_pqrs["nombre_cliente"] = texto_usuario
        estado_actual = "esperando_foto_factura"
        respuesta_bot = (
            "Finalmente, debes adjuntar obligatoriamente una foto de la *tirilla de compra* (factura física).\n"
            "Si no la tienes, debes acercarte al punto de venta y solicitarla ya que para este proceso es estrictamente necesaria.\n\n"
            "(📸 *Envía la foto de la tirilla* ahora mismo aquí en el chat)."
        )
        botones_bot = ["No tengo la foto", "Volver"]

    elif estado_actual == "esperando_foto_factura":
        if texto == "no tengo la foto" or ("[imagen_url]:" not in texto and "[documento_url]:" not in texto):
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = "⚠️ Sin la foto de la tirilla de compra no podemos procesar la solicitud. Debes acercarte al punto de venta y solicitarla ya que para este proceso es necesaria.\n\nEl proceso ha sido cancelado."
            botones_bot = ["Menú Principal", "Finalizar"]
        else:
            tiene_foto = texto.split("]:")[1] if "]:" in texto else texto
            
            correo_f = datos_pqrs.get("correo_franquiciado", SMTP_USER)
            local_nombre = datos_pqrs.get("local", "Cosechas")
            nit_guardar = datos_pqrs.get("nit")
            nombre_cliente = datos_pqrs.get("nombre_cliente", "No especificado")
            correo_cliente = datos_pqrs.get("correo_cliente", "No especificado")
            documento = datos_pqrs.get("documento_factura", "")
            
            detalle = f"Solicitud de Facturación Electrónica.\nDocumento/NIT: {documento}"
            numero_radicado = "PENDIENTE"
            
            try:
                respuesta_insert = supabase.table("tickets_pqrs").insert({
                    "celular_cliente": celular, "nit_franquiciado": nit_guardar, "nombre_franquicia": local_nombre,
                    "tipo_reporte": "Sugerencia", "motivo": "Servicio",
                    "tipo_novedad": "Factura electrónica", "detalle": detalle, "evidencia": tiene_foto,
                    "nombre_cliente": nombre_cliente, "correo_cliente": correo_cliente
                }).execute()
                if respuesta_insert.data:
                    numero_radicado = str(respuesta_insert.data[0]['id'])
            except Exception as e:
                print(f"Error DB Factura: {e}")
                
            try:
                tipo_completo = "Solicitud Factura Electrónica"
                destinatario_interno = "servicioalcliente@cosechasexpress.com"
                nombre_area = "Coordinación de Servicio al Cliente"
                correos_internos_str = destinatario_interno
                
                enviar_correo_pqrs_franquiciado(correo_f, numero_radicado, tipo_completo, detalle, local_nombre, celular, destinatario_interno, nombre_area, nombre_cliente, correo_cliente)
                enviar_correo_pqrs_interno(correos_internos_str, numero_radicado, tipo_completo, detalle, local_nombre, celular, nombre_area, nombre_cliente, correo_cliente)
            except Exception as e:
                print("Error enviando correo factura:", e)
                
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = f"✅ *Solicitud de Facturación Recibida*\n*Ticket: #{numero_radicado}*\n\nTu solicitud y la foto de la tirilla han sido enviadas. Se procesará pronto."
            botones_bot = ["Menú Principal", "Finalizar"]

    elif estado_actual == "esperando_nombre_pqrs":
        datos_pqrs["nombre_cliente"] = texto_usuario
        estado_actual = "esperando_correo_pqrs"
        respuesta_bot = f"Gracias, {texto_usuario.split()[0].capitalize()}. Ahora por favor escríbeme tu *Correo Electrónico* para notificarte sobre la respuesta a tu caso:\n\n*(Si no tienes o no deseas darlo, toca 'Saltar Correo')*"
        botones_bot = ["Saltar Correo", "Volver"]

    elif estado_actual == "esperando_correo_pqrs":
        correo = None if texto == "saltar correo" else texto_usuario
        datos_pqrs["correo_cliente"] = correo
        estado_actual = "esperando_detalle_pqrs"
        respuesta_bot = "¡Perfecto! Ahora, por favor *escribe en un solo mensaje* el detalle exacto de lo sucedido:\n\n*(Si deseas cancelar, toca 'Volver')*"
        botones_bot = ["Volver"]

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

        correo_f = datos_pqrs.get("correo_franquiciado", SMTP_USER)
        tipo = datos_pqrs.get("tipo", "No especificado")
        tipo_reporte = datos_pqrs.get("tipo_reporte", "Novedad")
        motivo = datos_pqrs.get("motivo", None)
        
        detalle = datos_pqrs.get("detalle", "")
        nit_guardar = datos_pqrs.get("nit")
        local_nombre = datos_pqrs.get("local", "Cosechas")
        nombre_cliente = datos_pqrs.get("nombre_cliente", "No especificado")
        correo_cliente = datos_pqrs.get("correo_cliente", "No especificado")
        
        destinatario_interno = "servicioalcliente@cosechasexpress.com"
        nombre_area = "Coordinación de Servicio al Cliente"

        # Armar las listas separadas
        correo_franquiciado_str = correo_f
        correos_internos_str = destinatario_interno
        
        numero_radicado = "PENDIENTE"

        # --- SEPARACIÓN TÉCNICA 1: Inserción en DB ---
        try:
            respuesta_insert = supabase.table("tickets_pqrs").insert({
                "celular_cliente": celular, "nit_franquiciado": nit_guardar, "nombre_franquicia": local_nombre,
                "tipo_reporte": tipo_reporte, "motivo": motivo,
                "tipo_novedad": tipo, "detalle": detalle, "evidencia": tiene_foto,
                "nombre_cliente": nombre_cliente, "correo_cliente": correo_cliente
            }).execute()
            
            if respuesta_insert.data:
                numero_radicado = str(respuesta_insert.data[0]['id'])
        except Exception as e:
            print(f"❌ Error en DB (Posible Foreign Key): {e}")

        # --- SEPARACIÓN TÉCNICA 2: Envío de Correos Independientes ---
        try:
            tipo_completo = f"{tipo_reporte} ({motivo}) - {tipo}" if motivo else f"{tipo_reporte} - {tipo}"
            
            # 1. Al Franquiciado
            enviar_correo_pqrs_franquiciado(correo_franquiciado_str, numero_radicado, tipo_completo, detalle, local_nombre, celular, destinatario_interno, nombre_area, nombre_cliente, correo_cliente)
            
            # 2. Al Equipo Interno
            if correos_internos_str:
                enviar_correo_pqrs_interno(correos_internos_str, numero_radicado, tipo_completo, detalle, local_nombre, celular, nombre_area, nombre_cliente, correo_cliente)
                
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

    elif estado_actual == "esperando_nombre_franquicia":
        datos_pqrs["nombre_franquicia"] = texto_usuario
        estado_actual = "esperando_ciudad_franquicia"
        respuesta_bot = f"Mucho gusto, {texto_usuario.split()[0].capitalize()}. Ahora dime:\n\n📍 *¿En qué ciudad te gustaría abrir tu franquicia Cosechas?*"
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_ciudad_franquicia":
        datos_pqrs["ciudad_franquicia"] = texto_usuario
        estado_actual = "esperando_correo_franquicia"
        respuesta_bot = "¡Perfecto! Por favor escríbeme tu *Correo electrónico* para que nuestros asesores puedan contactarte:"
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_correo_franquicia":
        datos_pqrs["correo_franquicia"] = texto_usuario
        estado_actual = "esperando_tipo_interes_franquicia"
        respuesta_bot = "¿Estás interesado en abrir una Nueva Franquicia o prefieres una que ya esté En Operación?"
        botones_bot = ["Nueva Franquicia", "En operación"]

    elif estado_actual == "esperando_tipo_interes_franquicia":
        opciones_validas = ["nueva franquicia", "en operación", "en operacion"]
        if texto in opciones_validas:
            val = "Nueva Franquicia" if "nueva" in texto else "En operación"
            datos_pqrs["tipo_franquicia"] = val
            
            if val == "En operación":
                guardar_lead_franquicia(celular, datos_pqrs)
                estado_actual = "menu_opciones"
                datos_pqrs = {}
                respuesta_bot = "Uno de nuestros agentes se contactará contigo para brindarte más información sobre las franquicias en operación.\n\n¿Deseas consultar algo más?"
                botones_bot = ["Menú Principal", "Finalizar"]
            else:
                estado_actual = "esperando_interes_pdf_franquicia"
                respuesta_bot = "Te invito a revisar nuestra presentación oficial de franquicias.\n\nTras conocer nuestro modelo, ¿sigues interesado?"
                documento_bot = {
                    "url": f"{R2_PUBLIC_URL}/presentacion/PRESENTACION FRANQUICIAS 2026_v2.pdf",
                    "nombre": "PRESENTACION FRANQUICIAS 2026_v2.pdf"
                }
                botones_bot = ["Sí, estoy interesado", "No, gracias"]
        else:
            respuesta_bot = "⚠️ Por favor selecciona una opción:"
            botones_bot = ["Nueva Franquicia", "En operación"]

    elif estado_actual == "esperando_interes_pdf_franquicia":
        opciones_validas = ["sí, estoy interesado", "si, estoy interesado", "no, gracias"]
        if texto in opciones_validas:
            if "no" in texto:
                estado_actual = "menu_opciones"
                datos_pqrs = {}
                respuesta_bot = "Muchas gracias por tu tiempo.\n\n¿Deseas consultar algo más?"
                botones_bot = ["Menú Principal", "Finalizar"]
            else:
                estado_actual = "esperando_local_franquicia"
                respuesta_bot = "¿Ya tienes un local identificado para abrir?"
                botones_bot = ["Sí", "No"]
        else:
            respuesta_bot = "⚠️ Por favor selecciona una opción:"
            botones_bot = ["Sí, estoy interesado", "No, gracias"]

    elif estado_actual == "esperando_local_franquicia":
        opciones_validas = ["sí", "si", "no"]
        if texto in opciones_validas:
            val = "Sí" if "si" in texto or "sí" in texto else "No"
            datos_pqrs["local_identificado"] = val
            
            if val == "No":
                estado_actual = "esperando_contacto_sin_local_franquicia"
                respuesta_bot = "Muchas gracias, tus datos han sido tomados.\n\nTen en cuenta que en Cosechas no nos hacemos cargo de la búsqueda del local.\n\n¿Deseas que un agente se comunique contigo?"
                botones_bot = ["Contactarme", "Menú Principal", "Finalizar"]
            else:
                estado_actual = "esperando_direccion_local_franquicia"
                respuesta_bot = "Por favor escribe la *dirección completa* y el *barrio* del local:"
                botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ Por favor selecciona una opción:"
            botones_bot = ["Sí", "No"]

    elif estado_actual == "esperando_contacto_sin_local_franquicia":
        opciones_validas = ["contactarme", "menú principal", "menu principal", "finalizar"]
        if any(op in texto for op in opciones_validas):
            if "contactarme" in texto:
                guardar_lead_franquicia(celular, datos_pqrs)
                estado_actual = "menu_opciones"
                datos_pqrs = {}
                respuesta_bot = "Tus datos han sido enviados a nuestros asesores. Muy pronto se comunicarán contigo.\n\n¿Deseas consultar algo más?"
                botones_bot = ["Menú Principal", "Finalizar"]
            elif "finalizar" in texto:
                estado_actual = "menu_principal"
                datos_pqrs = {}
                respuesta_bot = "¡Gracias por comunicarte con Cosechas! Que tengas un excelente día. 👋"
            else:
                # "Menu principal"
                estado_actual = "menu_principal"
                datos_pqrs = {}
                respuesta_bot = "¿En qué más te puedo ayudar?"
                botones_bot = ["Menú y Precios", "Radicar PQRS", "Franquicias Col"]
        else:
            respuesta_bot = "⚠️ Por favor selecciona una opción:"
            botones_bot = ["Contactarme", "Menú Principal", "Finalizar"]
            
    elif estado_actual == "esperando_direccion_local_franquicia":
        datos_pqrs["direccion_local"] = texto_usuario
        estado_actual = "esperando_foto_local_franquicia"
        respuesta_bot = "Por favor, envíame una *foto general donde se vea la fachada* del local:"
        botones_bot = ["No tengo la foto", "Volver"]
        
    elif estado_actual == "esperando_foto_local_franquicia":
        if "[imagen_url]:" in texto:
            url_foto = texto.split("]:")[1].strip()
            datos_pqrs["foto_local"] = url_foto
            estado_actual = "esperando_involucramiento_franquicia"
            respuesta_bot = "¡Foto recibida! 📸\n\n¿Qué nivel de involucramiento tendrías en el negocio?"
            botones_bot = ["Directo", "Supervisión", "Inversión pasiva"]
        elif "no tengo la foto" in texto or "no tengo foto" in texto:
            datos_pqrs["foto_local"] = "No adjuntó foto"
            estado_actual = "esperando_involucramiento_franquicia"
            respuesta_bot = "¿Qué nivel de involucramiento tendrías en el negocio?"
            botones_bot = ["Directo", "Supervisión", "Inversión pasiva"]
        elif "volver" in texto:
            estado_actual = "esperando_direccion_local_franquicia"
            respuesta_bot = "Por favor escribe la *dirección completa* y el *barrio* del local:"
            botones_bot = ["Volver"]
        else:
            respuesta_bot = "⚠️ No detecté una imagen válida.\n\nPor favor envía la *foto de la fachada* desde el clip 📎 de tu WhatsApp, o toca 'Sin foto'."
            botones_bot = ["Sin foto", "Volver"]

    elif estado_actual == "esperando_involucramiento_franquicia":
        opciones_validas = ["directo", "supervisión", "supervision", "inversión pasiva", "inversion pasiva"]
        if texto in opciones_validas:
            if "directo" in texto: val = "Directo"
            elif "supervis" in texto: val = "Supervisión"
            else: val = "Inversión pasiva"
            
            datos_pqrs["involucramiento"] = val
            
            guardar_lead_franquicia(celular, datos_pqrs)
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = "Tus datos han sido tomados. Uno de nuestros agentes se comunicará contigo próximamente.\n\n¿Deseas consultar algo más?"
            botones_bot = ["Menú Principal", "Finalizar"]
        else:
            respuesta_bot = "⚠️ Por favor selecciona una opción:"
            botones_bot = ["Directo", "Supervisión", "Inversión pasiva"]

    elif estado_actual == "esperando_area_trabajo":
        if texto in ["punto de venta", "punto de venta "]:
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = (
                "Entendido. Te informamos que cada punto de venta realiza sus contrataciones de forma independiente, por lo que debes acercarte al punto que quieras o más te sirva y entregar allí tu hoja de vida impresa.\n\n"
                "¡Mucho éxito en tu búsqueda! 🌱"
            )
            botones_bot = ["Menú Principal", "Finalizar"]
        elif texto in ["planta cosechas", "planta cosechas "]:
            estado_actual = "esperando_ciudad_corporativo"
            datos_pqrs["tipo_empleo"] = "Planta Cosechas"
            respuesta_bot = "Estas son nuestras sedes principales.\nPor favor, indícanos en qué ciudad te interesaría:"
            botones_bot = ["Medellín", "Bogotá"]
        else:
            respuesta_bot = "⚠️ Opción no reconocida. Por favor, selecciona una:"
            botones_bot = ["Punto de Venta", "Planta Cosechas"]

    elif estado_actual == "esperando_ciudad_corporativo":
        if texto in ["medellín", "medellin", "bogotá", "bogota"]:
            datos_pqrs["ciudad_corporativo"] = "Medellín" if texto in ["medellín", "medellin"] else "Bogotá"
            estado_actual = "esperando_nombre_corporativo"
            respuesta_bot = "Entendido. Ahora por favor, escribe tu *Nombre Completo*:"
            botones_bot = ["Volver"]
        else:
            datos_pqrs["ciudad_corporativo"] = texto_usuario
            estado_actual = "confirmando_ciudad_corporativo"
            respuesta_bot = (
                "⚠️ Te informamos que actualmente solo contamos con centros operativos en Medellín y Bogotá.\n\n"
                "¿Aún estás interesado(a) en continuar con tu postulación?"
            )
            botones_bot = ["Sí", "No"]

    elif estado_actual == "confirmando_ciudad_corporativo":
        if texto in ["sí", "si", "si estoy interesado"]:
            estado_actual = "esperando_nombre_corporativo"
            respuesta_bot = "¡Perfecto! Ahora por favor, escribe tu *Nombre Completo*:"
            botones_bot = ["Volver"]
        elif texto in ["no", "ya no"]:
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = "Entendido. ¡Gracias por tu interés en Cosechas y mucho éxito en tu búsqueda laboral! 🌱"
            botones_bot = ["Volver", "Finalizar"]
        else:
            respuesta_bot = "⚠️ Opción no reconocida. ¿Aún estás interesado(a) en continuar?"
            botones_bot = ["Sí", "No"]

    elif estado_actual == "esperando_nombre_corporativo":
        datos_pqrs["nombre_candidato"] = texto_usuario
        estado_actual = "esperando_cv_corporativo"
        respuesta_bot = (
            f"Gracias, {texto_usuario.split()[0].capitalize()}.\n\n"
            "Para completar tu postulación al área Operativa, necesitamos tu Hoja de Vida. 📄\n\n"
            "Por favor, *adjunta y envía tu Hoja de Vida en formato PDF o Imagen* ahora mismo aquí en el chat."
        )
        botones_bot = ["Volver"]

    elif estado_actual == "esperando_cv_corporativo":
        url_archivo = None
        if "[documento_url]:" in texto:
            url_archivo = texto.split("]:")[1]
        elif "[imagen_url]:" in texto:
            url_archivo = texto.split("]:")[1]
            
        if not url_archivo:
            respuesta_bot = "⚠️ No detecté un archivo válido.\n\nPor favor, adjunta el documento PDF de tu Hoja de Vida usando el ícono de clip 📎."
            botones_bot = ["Volver"]
        else:
            nombre = datos_pqrs.get("nombre_candidato", "No especificado")
            ciudad = datos_pqrs.get("ciudad_corporativo", "No especificada")
            try:
                supabase.table("candidatos_corporativos").insert({
                    "celular": celular, "nombre": nombre, "url_pdf": url_archivo, "ciudad": ciudad
                }).execute()
                # Enviar correo a RRHH
                enviar_correo_hoja_vida(nombre, celular, url_archivo, ciudad)
            except Exception as e:
                print("Error al guardar CV corporativo:", e)
                
            estado_actual = "menu_opciones"
            datos_pqrs = {}
            respuesta_bot = (
                "✅ *¡Postulación Exitosa!*\n\n"
                "Hemos recibido tu Hoja de Vida y ha sido enviada directamente a Talento Humano.\n\n"
                "Ellos se encargarán de revisarla y se comunicarán contigo en caso de cumplir con el perfil de alguna vacante vigente.\n\n"
                "¡Mucho éxito! 🌱😉🌱"
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