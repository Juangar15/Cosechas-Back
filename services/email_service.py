import smtplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
# Importamos la nueva variable EMAIL_EXPANSION
from config import EMAIL_USER, EMAIL_PASS, EMAIL_EXPANSION 
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def log_retry_email(retry_state):
    print(f"⚠️ Reintentando envío de correo SMTP (Intento {retry_state.attempt_number}/3) debido a: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(smtplib.SMTPException), before_sleep=log_retry_email, reraise=True)
def enviar_correo_pqrs_franquiciado(destinatario: str, radicado: str, tipo: str, detalle: str, local: str, celular: str, correo_interno: str, nombre_area: str, nombre_cliente: str, correo_cliente: str):
    mensaje = MIMEMultipart("alternative")
    mensaje['From'] = f"Cosechas PQRS <{EMAIL_USER}>"
    mensaje['To'] = destinatario 
    mensaje['Subject'] = f"🟢 Nuevo Reporte PQRS #{radicado} - {local} ({tipo})"
    mensaje['Date'] = email.utils.formatdate(localtime=True)
    mensaje['Message-ID'] = email.utils.make_msgid()
    
    # Codificar el asunto para evitar problemas con Office 365
    asunto_raw = f"[Seguimiento PQRS #{radicado}] - Sede {local}"
    asunto_encoded = urllib.parse.quote(asunto_raw)

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Montserrat', 'Century Gothic', Arial, sans-serif; color: #3f2c23; line-height: 1.6; margin: 0; padding: 0; background-color: #f8fafc; }}
            .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #f1f5f9; }}
            .header {{ background: linear-gradient(135deg, #ed1650 0%, #bb4699 100%); color: #ffffff; padding: 30px 20px; text-align: center; }}
            .header h2 {{ margin: 0; font-size: 24px; letter-spacing: 1px; font-weight: 800; text-transform: uppercase; font-family: 'Nunito', 'Century Gothic', sans-serif; }}
            .header p {{ margin: 5px 0 0 0; font-size: 14px; opacity: 0.9; }}
            .content {{ padding: 35px 30px; }}
            .salutation {{ font-size: 18px; margin-bottom: 25px; color: #1e293b; font-weight: 600; }}
            .details-box {{ background-color: #fff1f2; border-left: 6px solid #ed1650; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
            .details-table {{ width: 100%; border-collapse: collapse; }}
            .details-table td {{ padding: 10px 0; font-size: 15px; border-bottom: 1px solid #ffe4e6; }}
            .details-table tr:last-child td {{ border-bottom: none; }}
            .highlight {{ font-weight: bold; color: #ed1650; width: 140px; display: inline-block; }}
            .badge-alegria {{ background-color: #ffee00; color: #6d236a; padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: bold; display: inline-block; }}
            .detalle-texto {{ background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #ffe4e6; margin-top: 15px; font-style: italic; color: #475569; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); }}
            .alert-box {{ background-color: #f7fee7; border: 1px solid #ecfccb; border-left: 6px solid #9eca3a; padding: 20px; border-radius: 8px; font-size: 14px; color: #3f6212; margin-top: 30px; }}
            .alert-box strong {{ color: #4d7c0f; }}
            .btn-action {{ display: inline-block; background-color: #9eca3a; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; margin-top: 15px; text-align: center; box-shadow: 0 4px 6px -1px rgba(158, 202, 58, 0.4); }}
            .footer {{ background-color: #f1f5f9; text-align: center; padding: 25px 20px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Mesa de Ayuda Cosechas</h2>
                <p>Gestión de Novedades y PQRS</p>
            </div>
            <div class="content">
                <p class="salutation">Hola, Sr(a) Franquiciado de la tienda {local} 👋</p>
                <p>El asistente virtual ha registrado un nuevo reporte en su tienda. A continuación, presentamos los detalles del caso para su conocimiento:</p>
                
                <div class="details-box">
                    <table class="details-table">
                        <tr><td width="35%"><span class="highlight">🎫 Radicado:</span></td><td width="65%"><strong>#{radicado}</strong></td></tr>
                        <tr><td><span class="highlight">⚠️ Categoría:</span></td><td><span class="badge-alegria">{tipo}</span></td></tr>
                    </table>
                    <div class="detalle-texto">"{detalle}"</div>
                </div>

                <div class="alert-box">
                    <strong style="color: #b91c1c;">⚠️ ACCIÓN OBLIGATORIA REQUERIDA</strong><br><br>
                    Le informamos que este caso ha sido registrado en su tienda y reportado a <strong>{nombre_area} Cosechas Máster</strong>.<br><br>
                    Para garantizar los estándares de servicio de la franquicia, <strong>ES DE CARÁCTER OBLIGATORIO</strong> que usted se comunique oportunamente con el Coordinador de Servicio al Cliente para gestionar este caso en un plazo <strong>MÁXIMO de 4 días hábiles</strong>.<br><br>
                    Por favor, póngase en contacto a través del siguiente botón indicando su número de radicado:
                    <br>
                    <a href="mailto:{correo_interno}?subject={asunto_encoded}" class="btn-action">
                        Contactar a {nombre_area}
                    </a>
                    <br><br>
                    <span style="font-size: 12px; color: #64748b; font-style: italic;">
                        (Si el botón no funciona en su gestor de correo, escriba directamente a: <strong>{correo_interno}</strong>)
                    </span>
                </div>
            </div>
            <div class="footer"><p>Este es un mensaje automático generado por el sistema de <strong>Cosechas Colombia</strong>.<br>Por favor, no responder a este correo.</p></div>
        </div>
    </body>
    </html>
    """
    mensaje.attach(MIMEText(cuerpo_html, 'html'))
    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_USER, EMAIL_PASS)
        servidor.sendmail(EMAIL_USER, [destinatario.strip()], mensaje.as_string())
        servidor.quit()
        return True
    except Exception as e:
        print(f"❌ Error al enviar correo a franquiciado: {e}")
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(smtplib.SMTPException), before_sleep=log_retry_email, reraise=True)
def enviar_correo_pqrs_interno(destinatarios: str, radicado: str, tipo: str, detalle: str, local: str, celular: str, nombre_area: str, nombre_cliente: str, correo_cliente: str):
    mensaje = MIMEMultipart("alternative")
    mensaje['From'] = f"Cosechas PQRS <{EMAIL_USER}>"
    mensaje['To'] = destinatarios 
    mensaje['Subject'] = f"🟢 Nuevo Reporte Asignado #{radicado} - {local} ({tipo})"
    mensaje['Date'] = email.utils.formatdate(localtime=True)
    mensaje['Message-ID'] = email.utils.make_msgid()

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Montserrat', 'Century Gothic', Arial, sans-serif; color: #3f2c23; line-height: 1.6; margin: 0; padding: 0; background-color: #f8fafc; }}
            .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #f1f5f9; }}
            .header {{ background: linear-gradient(135deg, #ed1650 0%, #bb4699 100%); color: #ffffff; padding: 30px 20px; text-align: center; }}
            .header h2 {{ margin: 0; font-size: 24px; letter-spacing: 1px; font-weight: 800; text-transform: uppercase; font-family: 'Nunito', 'Century Gothic', sans-serif; }}
            .content {{ padding: 35px 30px; }}
            .salutation {{ font-size: 18px; margin-bottom: 25px; color: #1e293b; font-weight: 600; }}
            .details-box {{ background-color: #fff1f2; border-left: 6px solid #ed1650; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
            .details-table {{ width: 100%; border-collapse: collapse; }}
            .details-table td {{ padding: 10px 0; font-size: 15px; border-bottom: 1px solid #ffe4e6; }}
            .details-table tr:last-child td {{ border-bottom: none; }}
            .highlight {{ font-weight: bold; color: #ed1650; width: 140px; display: inline-block; }}
            .badge-alegria {{ background-color: #ffee00; color: #6d236a; padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: bold; display: inline-block; }}
            .detalle-texto {{ background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #ffe4e6; margin-top: 15px; font-style: italic; color: #475569; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); }}
            .alert-box {{ background-color: #f7fee7; border: 1px solid #ecfccb; border-left: 6px solid #9eca3a; padding: 20px; border-radius: 8px; font-size: 14px; color: #3f6212; margin-top: 30px; }}
            .alert-box strong {{ color: #4d7c0f; }}
            .footer {{ background-color: #f1f5f9; text-align: center; padding: 25px 20px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Alerta Operativa PQRS</h2>
            </div>
            <div class="content">
                <p class="salutation">Hola, equipo de {nombre_area} 👋</p>
                <p>Se ha generado un nuevo reporte PQRS asignado a su área correspondiente a la tienda <strong>{local}</strong>. A continuación los detalles:</p>
                
                <div class="details-box">
                    <table class="details-table">
                        <tr><td width="35%"><span class="highlight">🎫 Radicado:</span></td><td width="65%"><strong>#{radicado}</strong></td></tr>
                        <tr><td><span class="highlight">👤 Nombre:</span></td><td>{nombre_cliente}</td></tr>
                        <tr><td><span class="highlight">📱 Contacto:</span></td><td>{celular}</td></tr>
                        <tr><td><span class="highlight">✉️ Correo:</span></td><td>{correo_cliente}</td></tr>
                        <tr><td><span class="highlight">⚠️ Categoría:</span></td><td><span class="badge-alegria">{tipo}</span></td></tr>
                    </table>
                    <div class="detalle-texto">"{detalle}"</div>
                </div>

                <div class="alert-box">
                    <strong>📌 Acción Requerida:</strong><br><br>
                    {'Por favor, ingrese al Dashboard Operativo para realizar el seguimiento y cierre de este ticket una vez se haya solucionado con el franquiciado o el cliente.' if 'Gerencia' not in nombre_area else 'Por favor, ingrese al Dashboard Operativo para revisar los detalles de esta incidencia crítica (Servicio al Cliente es el encargado de gestionar su cierre en el sistema).'}
                </div>
            </div>
            <div class="footer"><p>Mensaje automático del bot de Cosechas.</p></div>
        </div>
    </body>
    </html>
    """
    mensaje.attach(MIMEText(cuerpo_html, 'html'))
    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_USER, EMAIL_PASS)
        lista_destinatarios = [c.strip() for c in destinatarios.split(",")]
        servidor.sendmail(EMAIL_USER, lista_destinatarios, mensaje.as_string())
        servidor.quit()
        print(f"✅ Correo HTML enviado a internos: {destinatarios}")
        return True
    except Exception as e:
        print(f"❌ Error general al enviar correo interno: {e}")
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(smtplib.SMTPException), before_sleep=log_retry_email, reraise=True)
def enviar_correo_nueva_franquicia(celular: str, ciudad: str, local_identificado: str, involucramiento: str, nombre: str, correo: str, tipo_franquicia: str, direccion_local: str, foto_local: str):
    mensaje = MIMEMultipart("alternative")
    mensaje['From'] = f"Expansión Cosechas <{EMAIL_USER}>"
    
    # Usamos la variable de entorno
    mensaje['To'] = EMAIL_EXPANSION 
    mensaje['Subject'] = f"🚀 Nuevo Lead de Franquicia ({tipo_franquicia}) - {ciudad}"

    # Estilo de color
    badge_lead = f"<span style='background-color: #9eca3a; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 18px;'>NUEVO LEAD</span>"

    # Botón de foto si aplica
    foto_html = ""
    if foto_local and foto_local != "No adjuntó foto" and "http" in foto_local:
        foto_html = f"<div style='text-align: center; margin-top: 20px;'><a href='{foto_local}' style='background-color: #ed1650; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;'>Ver Foto de Fachada</a></div>"
    elif foto_local:
        foto_html = f"<p><span class='highlight'>📸 Foto Fachada:</span> {foto_local}</p>"

    direccion_html = f"<p><span class='highlight'>📍 Dirección Local:</span> {direccion_local}</p>" if direccion_local else ""

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Montserrat', 'Century Gothic', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .header {{ background: linear-gradient(135deg, #9eca3a 0%, #23b24a 100%); color: #ffffff; padding: 25px; text-align: center; }}
            .header h2 {{ margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px; font-family: 'Nunito', 'Century Gothic', sans-serif; }}
            .content {{ padding: 30px; }}
            .lead-box {{ background-color: #f7fee7; border-left: 5px solid #9eca3a; padding: 20px; border-radius: 0 8px 8px 0; margin: 20px 0; }}
            .lead-box p {{ margin: 10px 0; font-size: 15px; }}
            .highlight {{ font-weight: bold; color: #4d7c0f; display: inline-block; width: 150px; }}
            .footer {{ background-color: #f1f5f9; text-align: center; padding: 15px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
            .lead-score {{ text-align: center; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🚀 Nuevo Prospecto de Franquicia</h2>
            </div>
            <div class="content">
                <p>Hola, equipo de Expansión. Un nuevo prospecto ha sido contactado a través del asistente virtual de WhatsApp.</p>
                
                <div class="lead-score">
                    {badge_lead}
                </div>

                <div class="lead-box">
                    <h3 style="margin-top: 0; color: #334155; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">Datos de Contacto</h3>
                    <p><span class="highlight">👤 Nombre:</span> {nombre}</p>
                    <p><span class="highlight">📱 Celular:</span> {celular}</p>
                    <p><span class="highlight">✉️ Correo:</span> {correo}</p>
                    <p><span class="highlight">🌆 Ciudad:</span> {ciudad}</p>
                    
                    <h3 style="margin-top: 20px; color: #334155; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">Perfil e Interés</h3>
                    <p><span class="highlight">🎯 Interés:</span> {tipo_franquicia}</p>
                    <p><span class="highlight">🏢 Tiene Local:</span> {local_identificado}</p>
                    {direccion_html}
                    <p><span class="highlight">🤝 Involucramiento:</span> {involucramiento}</p>
                    {foto_html}
                </div>
            </div>
            <div class="footer">Generado automáticamente por el Bot de Cosechas</div>
        </div>
    </body>
    </html>
    """
    mensaje.attach(MIMEText(cuerpo_html, 'html'))

    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_USER, EMAIL_PASS)
        
        # AQUÍ ESTABA EL ERROR: Pasamos la variable en lugar del string quemado
        servidor.sendmail(EMAIL_USER, [EMAIL_EXPANSION], mensaje.as_string())
        
        servidor.quit()
        print(f"✅ Correo de franquicia enviado exitosamente a: {EMAIL_EXPANSION}")
    except smtplib.SMTPException as e:
        print(f"❌ Error SMTP al enviar correo de franquicia, se reintentará: {e}")
        raise
    except Exception as e:
        print(f"❌ Error general al enviar correo de franquicia: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(smtplib.SMTPException), before_sleep=log_retry_email, reraise=True)
def enviar_correo_hoja_vida(nombre: str, celular: str, url_pdf: str, ciudad: str):
    mensaje = MIMEMultipart("alternative")
    mensaje['From'] = f"Talento Humano Cosechas <{EMAIL_USER}>"
    mensaje['To'] = "3113816216juanjose@gmail.com"
    mensaje['Subject'] = f"📄 Nuevo Candidato Sede Corporativa - {nombre}"

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Montserrat', 'Century Gothic', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; padding: 25px; text-align: center; }}
            .header h2 {{ margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px; font-family: 'Nunito', 'Century Gothic', sans-serif; }}
            .content {{ padding: 30px; }}
            .lead-box {{ background-color: #ecfdf5; border-left: 5px solid #10b981; padding: 20px; border-radius: 0 8px 8px 0; margin: 20px 0; }}
            .lead-box p {{ margin: 10px 0; font-size: 15px; }}
            .highlight {{ font-weight: bold; color: #047857; display: inline-block; width: 130px; }}
            .btn-action {{ display: inline-block; background-color: #10b981; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; margin-top: 15px; text-align: center; }}
            .footer {{ background-color: #f1f5f9; text-align: center; padding: 15px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>📄 Nuevo Candidato Corporativo</h2>
            </div>
            <div class="content">
                <p>Hola, Talento Humano. Un nuevo candidato ha completado el formulario a través del asistente virtual de WhatsApp y ha adjuntado su hoja de vida.</p>
                <div class="lead-box">
                    <p><span class="highlight">👤 Nombre:</span> {nombre}</p>
                    <p><span class="highlight">📱 Celular:</span> {celular}</p>
                    <p><span class="highlight">🌆 Ciudad:</span> {ciudad}</p>
                </div>
                <center>
                    <a href="{url_pdf}" class="btn-action">Descargar Hoja de Vida (PDF)</a>
                </center>
            </div>
            <div class="footer">Generado automáticamente por el Bot de Cosechas</div>
        </div>
    </body>
    </html>
    """
    mensaje.attach(MIMEText(cuerpo_html, 'html'))

    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_USER, EMAIL_PASS)
        servidor.sendmail(EMAIL_USER, ["3113816216juanjose@gmail.com"], mensaje.as_string())
        servidor.quit()
        print(f"✅ Correo de RRHH enviado exitosamente a: 3113816216juanjose@gmail.com")
    except smtplib.SMTPException as e:
        print(f"❌ Error SMTP al enviar correo de RRHH, se reintentará: {e}")
        raise
    except Exception as e:
        print(f"❌ Error general al enviar correo de RRHH: {e}")