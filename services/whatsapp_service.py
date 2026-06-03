import httpx
import uuid
from config import WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, supabase
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def log_retry(retry_state):
    print(f"⚠️ Reintentando API Meta (Intento {retry_state.attempt_number}/3) debido a: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), before_sleep=log_retry, reraise=True)
async def enviar_mensaje_whatsapp(celular_destino: str, texto_mensaje: str, interaccion = None):
    """
    Soporta botones rápidos (lista de hasta 3 strings) o menús desplegables (diccionario).
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("⚠️ Advertencia: Faltan credenciales de Meta en el archivo .env")
        return

    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. SI ES UN MENÚ DESPLEGABLE (LISTA)
    if isinstance(interaccion, dict) and interaccion.get("tipo") == "lista":
        rows = []
        for i, opcion in enumerate(interaccion["opciones"]):
            # NUEVO: Soporte para opciones enriquecidas (ID oculto y descripción)
            if isinstance(opcion, dict):
                rows.append({
                    "id": str(opcion.get("id", f"list_row_{i}"))[:200],
                    "title": str(opcion.get("title", ""))[:24],
                    "description": str(opcion.get("description", ""))[:72]
                })
            else:
                # Compatibilidad con las listas anteriores (strings normales)
                rows.append({
                    "id": f"list_row_{i}",
                    "title": str(opcion)[:24]
                })
            
        payload = {
            "messaging_product": "whatsapp",
            "to": celular_destino,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "Cosechas Colombia"},
                "body": {"text": texto_mensaje},
                "footer": {"text": "Toca el botón abajo para ver las opciones 👇"},
                "action": {
                    "button": interaccion.get("boton", "Ver Opciones")[:20],
                    "sections": [{"title": "Servicios Disponibles", "rows": rows}]
                }
            }
        }

    # 2. SI SON BOTONES RÁPIDOS
    elif isinstance(interaccion, list) and len(interaccion) <= 3:
        botones_formateados = []
        for i, titulo in enumerate(interaccion):
            botones_formateados.append({
                "type": "reply",
                "reply": {
                    "id": f"btn_{i}",
                    "title": titulo[:20]
                }
            })
            
        payload = {
            "messaging_product": "whatsapp",
            "to": celular_destino,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto_mensaje},
                "action": {"buttons": botones_formateados}
            }
        }
        
    # 3. TEXTO PLANO
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": celular_destino,
            "type": "text",
            "text": {"body": texto_mensaje}
        }
    
    try:
        async with httpx.AsyncClient() as client:
            respuesta = await client.post(url, headers=headers, json=payload)
            if respuesta.status_code >= 500:
                respuesta.raise_for_status() # Provoca el reintento
            elif respuesta.status_code == 200:
                print(f"✅ Mensaje enviado a {celular_destino} a través de Meta.")
            else:
                print("❌ Error de Meta al enviar (4xx):", respuesta.text)
    except httpx.RequestError as e:
        print("❌ Error de red con Meta API:", e)
        raise # Permitir que tenacity lo capture


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), before_sleep=log_retry, reraise=True)
async def enviar_documento_whatsapp(celular_destino: str, url_documento: str, nombre_archivo: str, texto_mensaje: str, botones: list = None):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("⚠️ Advertencia: Faltan credenciales de Meta en el archivo .env")
        return

    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if not botones:
        payload = {
            "messaging_product": "whatsapp",
            "to": celular_destino,
            "type": "document",
            "document": {
                "link": url_documento,
                "filename": nombre_archivo,
                "caption": texto_mensaje 
            }
        }
    else:
        botones_formateados = []
        for i, titulo in enumerate(botones):
            botones_formateados.append({
                "type": "reply",
                "reply": {"id": f"btn_doc_{i}", "title": titulo[:20]}
            })
            
        payload = {
            "messaging_product": "whatsapp",
            "to": celular_destino,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "document",
                    "document": {"link": url_documento, "filename": nombre_archivo}
                },
                "body": {"text": texto_mensaje},
                "action": {"buttons": botones_formateados}
            }
        }
    
    try:
        async with httpx.AsyncClient() as client:
            respuesta = await client.post(url, headers=headers, json=payload)
            if respuesta.status_code >= 500:
                respuesta.raise_for_status()
            elif respuesta.status_code == 200:
                print(f"✅ Documento unificado enviado a {celular_destino} exitosamente.")
            else:
                print("❌ Error de Meta al enviar documento unificado (4xx):", respuesta.text)
    except httpx.RequestError as e:
        print("❌ Error de red con Meta API al enviar documento:", e)
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), before_sleep=log_retry, reraise=True)
async def procesar_imagen_whatsapp(media_id: str) -> str:
    try:
        url_info = f"https://graph.facebook.com/v17.0/{media_id}"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        
        async with httpx.AsyncClient() as client:
            res_info_response = await client.get(url_info, headers=headers)
            if res_info_response.status_code >= 500:
                res_info_response.raise_for_status()
                
            res_info = res_info_response.json()
            
            if "url" not in res_info:
                return "Sin archivo"
                
            url_descarga = res_info["url"]
            res_img = await client.get(url_descarga, headers=headers)
            if res_img.status_code >= 500:
                res_img.raise_for_status()
                
            contenido_archivo = res_img.content
        
        nombre_unico = f"evidencia_wp_{uuid.uuid4()}.jpg"
        supabase.storage.from_("evidencias-pqrs").upload(
            path=nombre_unico,
            file=contenido_archivo,
            file_options={"content-type": "image/jpeg"}
        )
        
        return supabase.storage.from_("evidencias-pqrs").get_public_url(nombre_unico)
        
    except httpx.RequestError as e:
        print("Error de red procesando imagen desde WhatsApp:", e)
        raise
    except Exception as e:
        print("Error general procesando imagen desde WhatsApp:", e)
        return "Error de carga"