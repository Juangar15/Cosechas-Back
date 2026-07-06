from fastapi import APIRouter, Request, HTTPException, Body, BackgroundTasks
from fastapi.responses import PlainTextResponse
from config import WHATSAPP_VERIFY_TOKEN
from models import MensajePrueba
from services.bot_logic import procesar_mensaje_inteligente
from services.whatsapp_service import procesar_imagen_whatsapp, procesar_documento_whatsapp, enviar_documento_whatsapp, enviar_mensaje_whatsapp
import asyncio

router = APIRouter(tags=["webhook"])

@router.get("/webhook")
async def verificar_webhook_meta(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        print("¡Webhook verificado exitosamente por Meta!")
        return PlainTextResponse(content=challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Token inválido.")

async def procesar_y_responder(texto_cliente, celular_cliente):
    print(f"\n📲 PROCESANDO EN BACKGROUND -> REMITENTE: {celular_cliente} | VALOR: {texto_cliente}")
    try:
        respuesta_bot, botones_bot, documento_bot = procesar_mensaje_inteligente(texto_cliente, celular_cliente)
        if documento_bot:
            await enviar_documento_whatsapp(
                celular_destino=celular_cliente, 
                url_documento=documento_bot["url"], 
                nombre_archivo=documento_bot["nombre"],
                texto_mensaje=respuesta_bot,
                botones=botones_bot
            )
        else:
            await enviar_mensaje_whatsapp(celular_cliente, respuesta_bot, botones_bot)
    except Exception as e:
        print("Error en procesar_y_responder:", e)

@router.post("/webhook")
async def recibir_mensajes_whatsapp_real(background_tasks: BackgroundTasks, payload: dict = Body(...)):
    try:
        if payload.get("object") == "whatsapp_business_account":
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        mensaje_data = value["messages"][0]
                        celular_cliente = mensaje_data.get("from")
                        texto_cliente = ""
                        
                        if mensaje_data.get("type") == "text":
                            texto_cliente = mensaje_data["text"]["body"]
                            
                        elif mensaje_data.get("type") == "interactive":
                            interactive_type = mensaje_data["interactive"].get("type", "")
                            
                            if interactive_type == "button_reply":
                                texto_cliente = mensaje_data["interactive"]["button_reply"]["title"]
                                
                            elif interactive_type == "list_reply":
                                reply_id = mensaje_data["interactive"]["list_reply"].get("id", "")
                                if reply_id.startswith("nit_"):
                                    texto_cliente = reply_id
                                else:
                                    texto_cliente = mensaje_data["interactive"]["list_reply"].get("title", "")
                                
                        elif mensaje_data.get("type") == "image":
                            media_id = mensaje_data["image"]["id"]
                            url_publica = await procesar_imagen_whatsapp(media_id)
                            texto_cliente = f"[IMAGEN_URL]:{url_publica}"

                        elif mensaje_data.get("type") == "document":
                            media_id = mensaje_data["document"]["id"]
                            mime_type = mensaje_data["document"].get("mime_type", "application/pdf")
                            url_publica = await procesar_documento_whatsapp(media_id, mime_type)
                            texto_cliente = f"[DOCUMENTO_URL]:{url_publica}"

                        elif mensaje_data.get("type") == "location":
                            lat = mensaje_data["location"]["latitude"]
                            lon = mensaje_data["location"]["longitude"]
                            texto_cliente = f"[UBICACION]:{lat},{lon}"

                        if texto_cliente:
                            background_tasks.add_task(procesar_y_responder, texto_cliente, celular_cliente)
                            
        return {"status": "success"}
    except Exception as e:
        print("Error procesando el payload de Meta:", e)
        return {"status": "error"}

@router.post("/probar-bot")
async def probar_bot_local(mensaje: MensajePrueba):
    respuesta, botones, documento = procesar_mensaje_inteligente(mensaje.texto, mensaje.celular)
    return {
        "celular_cliente": mensaje.celular,
        "bot_responde": respuesta,
        "botones_sugeridos": botones,
        "documento_sugerido": documento
    }