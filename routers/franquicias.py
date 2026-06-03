from fastapi import APIRouter, HTTPException
from typing import Optional
from config import supabase
from models import ActualizarEstadoFranquicia

router = APIRouter(prefix="/api/franquicias", tags=["franquicias"])

@router.get("/solicitudes")
async def obtener_todas_las_solicitudes(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
):
    try:
        query = supabase.table("solicitudes_franquicia").select("*", count="exact")
        
        if estado:
            query = query.eq("estado", estado)
            
        if fecha_inicio:
            query = query.gte("fecha_creacion", f"{fecha_inicio}T00:00:00")
            
        if fecha_fin:
            query = query.lte("fecha_creacion", f"{fecha_fin}T23:59:59.999")
            
        if search:
            query = query.or_(f"celular.ilike.%{search}%,ciudad.ilike.%{search}%,direccion_local.ilike.%{search}%,dudas.ilike.%{search}%")
            
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        respuesta = query.order("fecha_creacion", desc=True).range(start, end).execute()
        
        return {
            "data": respuesta.data,
            "total": respuesta.count,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        print("Error al obtener solicitudes de franquicia:", e)
        raise HTTPException(status_code=500, detail="Error al consultar la base de datos.")

@router.put("/solicitudes/{solicitud_id}/estado")
async def actualizar_estado_solicitud(solicitud_id: int, datos: ActualizarEstadoFranquicia):
    # Estados lógicos para un CRM de ventas
    estados_validos = ["Pendiente", "Contactado", "Descartado"]
    if datos.nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail="Estado comercial inválido.")
        
    update_data = {"estado": datos.nuevo_estado}
    if datos.nota_resolucion is not None:
        update_data["nota_resolucion"] = datos.nota_resolucion

    try:
        respuesta_db = supabase.table("solicitudes_franquicia").update(update_data).eq("id", solicitud_id).execute()
        if len(respuesta_db.data) == 0:
            raise HTTPException(status_code=404, detail="El prospecto no existe.")
        return {"status": "success", "solicitud_actualizada": respuesta_db.data[0]}
    except Exception as e:
        print("Error al actualizar prospecto:", e)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")