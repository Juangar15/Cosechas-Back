from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from typing import Optional
import uuid
from config import supabase
from models import ActualizarEstado
from pydantic import BaseModel
from .dependencies import get_current_user
from services.email_service import enviar_correo_pqrs_franquiciado

class AsignarSede(BaseModel):
    nombre_sede: str

router = APIRouter(prefix="/api", tags=["tickets"])

@router.get("/tickets")
async def obtener_todos_los_tickets(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    categoria: Optional[str] = None,
    tipo_reporte: Optional[str] = None,
    motivo: Optional[str] = None,
    orden: Optional[str] = Query("desc", description="desc para más reciente, asc para más antiguo"),
    current_user: dict = Depends(get_current_user)
):
    try:
        rol = current_user.get("rol")
        
        # Seguridad: Restringir acceso basado en el rol
        if rol in ["espectador_sedes", "abogado_sedes", "especialista_leads", "sin_rol"]:
            raise HTTPException(status_code=403, detail="No tienes permisos para ver el módulo de PQRS.")

        query = supabase.table("tickets_pqrs").select("*", count="exact")
        
        # Filtro Inyectado por el Servidor para CAPACITADOR
        if rol == "capacitador":
            query = query.eq("motivo", "Producto").in_("tipo_novedad", ["Preparación", "Presentación del producto"])
            
        # Filtro Inyectado por el Servidor para GERENCIA JURÍDICA
        if rol == "gerencia_juridica":
            query = query.or_("tipo_novedad.eq.Objeto en el producto,motivo.eq.Objeto en el producto")
        
        if estado:
            query = query.eq("estado", estado)
            
        if tipo_reporte:
            query = query.eq("tipo_reporte", tipo_reporte)
            
        if motivo:
            query = query.eq("motivo", motivo)
            
        if categoria:
            query = query.eq("tipo_novedad", categoria)
            
        if fecha_inicio:
            query = query.gte("fecha_creacion", f"{fecha_inicio}T00:00:00")
            
        if fecha_fin:
            query = query.lte("fecha_creacion", f"{fecha_fin}T23:59:59.999")
            
        if search:
            query = query.or_(f"celular_cliente.ilike.%{search}%,detalle.ilike.%{search}%,nombre_franquicia.ilike.%{search}%,id.eq.{search if search.isdigit() else 0}")
            
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        respuesta = query.order("fecha_creacion", desc=(orden == "desc")).range(start, end).execute()
        
        return {
            "data": respuesta.data,
            "total": respuesta.count,
            "page": page,
            "page_size": page_size
        }
    except HTTPException:
        raise
    except Exception as e:
        print("Error al obtener tickets:", e)
        raise HTTPException(status_code=500, detail="Error al consultar la base de datos.")

@router.post("/upload")
async def subir_evidencia_pqrs(file: UploadFile = File(...)):
    try:
        contenido_archivo = await file.read()
        extension = file.filename.split(".")[-1]
        nombre_unico = f"evidencia_{uuid.uuid4()}.{extension}"
        
        supabase.storage.from_("evidencias-pqrs").upload(
            path=nombre_unico,
            file=contenido_archivo,
            file_options={"content-type": file.content_type}
        )
        url_publica_res = supabase.storage.from_("evidencias-pqrs").get_public_url(nombre_unico)
        return {"status": "success", "url_evidencia": url_publica_res}
    except Exception as e:
        print("Error al subir archivo a Storage:", e)
        raise HTTPException(status_code=500, detail="No se pudo almacenar la imagen.")

@router.put("/tickets/{ticket_id}/estado")
async def actualizar_estado_ticket(
    ticket_id: int, 
    estado_data: ActualizarEstado,
    current_user: dict = Depends(get_current_user)
):
    try:
        rol = current_user.get("rol")
        email = current_user.get("email")
        
        if rol in ["espectador_sedes", "abogado_sedes", "especialista_leads", "gerencia_juridica", "sin_rol"]:
            raise HTTPException(status_code=403, detail="No tienes permisos para editar PQRS.")

        update_payload = {
            "estado": estado_data.nuevo_estado,
            "cerrado_por_rol": rol,
            "cerrado_por_email": email
        }
        
        if estado_data.nota_resolucion is not None:
            update_payload["nota_resolucion"] = estado_data.nota_resolucion
            
        respuesta = supabase.table("tickets_pqrs").update(update_payload).eq("id", ticket_id).execute()
        if len(respuesta.data) == 0:
            raise HTTPException(status_code=404, detail="El ticket no existe.")
        return {"status": "success", "ticket_actualizado": respuesta.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        print("Error al actualizar estado:", e)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

@router.put("/tickets/{ticket_id}/asignar_sede")
async def asignar_sede_ticket(
    ticket_id: int,
    datos: AsignarSede,
    current_user: dict = Depends(get_current_user)
):
    try:
        rol = current_user.get("rol")
        if rol in ["espectador_sedes", "abogado_sedes", "especialista_leads", "sin_rol"]:
            raise HTTPException(status_code=403, detail="No tienes permisos.")

        # 1. Obtener la sede
        res_sede = supabase.table("sedes_oficiales").select("*").eq("ceco_nombre", datos.nombre_sede).execute()
        if not res_sede.data:
            raise HTTPException(status_code=404, detail="Sede no encontrada.")
        sede = res_sede.data[0]
        nit_franquiciado = sede.get("tercero_nit", "SIN_NIT")
        correo_franquiciado = sede.get("tercero_correo")

        # 2. Obtener el ticket original
        res_ticket = supabase.table("tickets_pqrs").select("*").eq("id", ticket_id).execute()
        if not res_ticket.data:
            raise HTTPException(status_code=404, detail="Ticket no encontrado.")
        ticket = res_ticket.data[0]

        # 3. Actualizar el ticket
        update_payload = {
            "nombre_franquicia": datos.nombre_sede,
            "nit_franquiciado": nit_franquiciado
        }
        res_upd = supabase.table("tickets_pqrs").update(update_payload).eq("id", ticket_id).execute()

        # 4. Enviar correo al franquiciado si tiene correo
        if correo_franquiciado:
            motivo = ticket.get("motivo")
            tipo = ticket.get("tipo_novedad")
            tipo_reporte = ticket.get("tipo_reporte")
            
            tipo_completo = f"{tipo_reporte} ({motivo}) - {tipo}" if motivo else f"{tipo_reporte} - {tipo}"
            
            destinatario_interno = "servicioalcliente@cosechasexpress.com"
            nombre_area = "Coordinación de Servicio al Cliente"
            
            if tipo == "Factura electrónica":
                tipo_completo = "Solicitud Factura Electrónica"
                destinatario_interno = "sistemas@cosechasexpress.com"
                nombre_area = "Sistemas"

            enviar_correo_pqrs_franquiciado(
                destinatario=correo_franquiciado,
                radicado=str(ticket_id),
                tipo=tipo_completo,
                detalle=ticket.get("detalle", ""),
                local=datos.nombre_sede,
                celular=ticket.get("celular_cliente", ""),
                correo_interno=destinatario_interno,
                nombre_area=nombre_area,
                nombre_cliente=ticket.get("nombre_cliente", ""),
                correo_cliente=ticket.get("correo_cliente", "")
            )

        return {"status": "success", "ticket_actualizado": res_upd.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        print("Error asignando sede:", e)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")