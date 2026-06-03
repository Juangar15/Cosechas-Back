from fastapi import APIRouter, HTTPException, Query
from config import supabase
from datetime import datetime, timedelta, timezone
from typing import Optional

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def is_within_period(date_str: str, periodo: str) -> bool:
    if not date_str:
        return False
    if not periodo or periodo == "historico":
        return True
        
    # Verificar si el periodo es un formato YYYY-MM
    if len(periodo) == 7 and "-" in periodo:
        try:
            date_col_clean = date_str.replace("Z", "+00:00")
            item_date = datetime.fromisoformat(date_col_clean)
            return item_date.strftime("%Y-%m") == periodo
        except Exception:
            pass
    
    try:
        clean_date_str = date_str.replace("Z", "+00:00")
        if "." in clean_date_str:
            base, ext = clean_date_str.split(".")
            ext_time, tz = ext[:6], ext[6:]
            if "+" in ext:
                ext_time, tz = ext.split("+")
                tz = "+" + tz
            elif "-" in ext:
                ext_time, tz = ext.split("-")
                tz = "-" + tz
            else:
                tz = ""
            clean_date_str = f"{base}.{ext_time}{tz}"
            
        item_date = datetime.fromisoformat(clean_date_str)
        now = datetime.now(timezone.utc)
        
        if periodo == "semana":
            return now - item_date <= timedelta(days=7)
        elif periodo == "mes":
            return now - item_date <= timedelta(days=30)
        elif periodo == "anio":
            return now - item_date <= timedelta(days=365)
    except Exception as e:
        print(f"Error parsing date {date_str}: {e}")
        pass
        
    return True

@router.get("/pqrs")
async def get_pqrs_analytics(periodo: Optional[str] = Query("historico", description="semana, mes, anio, historico")):
    try:
        respuesta = supabase.table("tickets_pqrs").select("*").execute()
        tickets = respuesta.data
        
        total = 0
        cerrados = 0
        
        for t in tickets:
            # Revisar columna de fecha
            date_col = t.get("fecha_creacion") or t.get("created_at")
            if is_within_period(date_col, periodo):
                total += 1
                if t.get("estado") == "Cerrado":
                    cerrados += 1
                    
        tasa_resolucion = round((cerrados / total * 100), 2) if total > 0 else 0.0
        
        return {
            "total": total,
            "cerrados": cerrados,
            "tasa_resolucion": tasa_resolucion
        }
    except Exception as e:
        print("Error analytics pqrs:", e)
        raise HTTPException(status_code=500, detail="Error interno.")

@router.get("/pqrs/mensual")
async def get_pqrs_mensual():
    """
    Retorna la tendencia mensual de PQRS a lo largo del tiempo.
    """
    try:
        respuesta = supabase.table("tickets_pqrs").select("fecha_creacion").execute()
        tickets = respuesta.data
        
        meses_count = {}
        # Mapeo para nombres de meses en español
        nombres_meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        
        for t in tickets:
            date_col = t.get("fecha_creacion") or t.get("created_at")
            if date_col:
                try:
                    clean_date_str = date_col.replace("Z", "+00:00")
                    item_date = datetime.fromisoformat(clean_date_str)
                    
                    # Formato: "Ene 26"
                    mes_str = f"{nombres_meses[item_date.month - 1]} {str(item_date.year)[2:]}"
                    sort_key = item_date.strftime("%Y-%m") # Para ordenar
                    
                    if sort_key not in meses_count:
                        meses_count[sort_key] = {"mes": mes_str, "cantidad": 0}
                        
                    meses_count[sort_key]["cantidad"] += 1
                except:
                    continue
                    
        # Ordenar cronológicamente
        sorted_keys = sorted(meses_count.keys())
        resultado = [meses_count[k] for k in sorted_keys]
        
        return resultado
    except Exception as e:
        print("Error analytics pqrs mensual:", e)
        raise HTTPException(status_code=500, detail="Error interno.")

@router.get("/pqrs/sedes")
async def get_pqrs_by_sede(
    periodo: Optional[str] = Query("historico", description="semana, mes, anio, historico"),
    limite: Optional[int] = Query(None, description="Número máximo de sedes a retornar (ej: 10 para el Top 10)")
):
    """
    Agrupa los PQRS por sede para identificar cuáles tienen más novedades.
    Aprovecha la relación con sedes_oficiales a través del nit_franquiciado.
    """
    try:
        # Se obtienen los tickets
        respuesta = supabase.table("tickets_pqrs").select("*").execute()
        tickets = respuesta.data
        
        sedes_count = {}
        
        for t in tickets:
            date_col = t.get("fecha_creacion") or t.get("created_at")
            if is_within_period(date_col, periodo):
                sede = t.get("nombre_franquicia") or "Sede Desconocida"
                nit = t.get("nit_franquiciado")
                
                # Usamos el nombre de la sede como llave, o podríamos usar el NIT
                if sede not in sedes_count:
                    sedes_count[sede] = {
                        "nit": nit,
                        "cantidad": 0
                    }
                
                sedes_count[sede]["cantidad"] += 1
                
        # Formatear el resultado como lista y ordenar de mayor a menor cantidad
        resultado = [
            {"sede": k, "nit": v["nit"], "cantidad": v["cantidad"]}
            for k, v in sedes_count.items()
        ]
        resultado.sort(key=lambda x: x["cantidad"], reverse=True)
        
        if limite is not None and limite > 0:
            resultado = resultado[:limite]
            
        return resultado
    except Exception as e:
        print("Error analytics pqrs por sedes:", e)
        raise HTTPException(status_code=500, detail="Error interno.")

@router.get("/sedes/imagen")
async def get_sedes_nueva_imagen():
    """
    Retorna la proporción de Sedes según su estado de Nueva Imagen (Sí, No, Próximo).
    Solo toma en cuenta sedes que estén 'OPERANDO'.
    """
    try:
        # Solo traemos las sedes en estado OPERANDO
        respuesta = supabase.table("sedes_oficiales").select("pdv_nueva_imagen").eq("pdv_estado", "OPERANDO").execute()
        sedes = respuesta.data
        
        imagen_count = {"Sí": 0, "No": 0, "Próximo": 0, "Otro": 0}
        
        for s in sedes:
            estado_img = s.get("pdv_nueva_imagen")
            if estado_img == "Sí":
                imagen_count["Sí"] += 1
            elif estado_img == "No":
                imagen_count["No"] += 1
            elif estado_img == "Próximo":
                imagen_count["Próximo"] += 1
            else:
                imagen_count["Otro"] += 1
                
        # Retornar en un formato listo para el PieChart
        resultado = []
        if imagen_count["Sí"] > 0: resultado.append({"name": "Sí", "value": imagen_count["Sí"]})
        if imagen_count["No"] > 0: resultado.append({"name": "No", "value": imagen_count["No"]})
        if imagen_count["Próximo"] > 0: resultado.append({"name": "Próximo", "value": imagen_count["Próximo"]})
        # Opcional: ignorar "Otro" o incluirlo si es necesario. Lo ignoraremos para enfocarnos en Si/No/Próximo.
        
        return resultado
    except Exception as e:
        print("Error analytics sedes imagen:", e)
        raise HTTPException(status_code=500, detail="Error interno.")

@router.get("/franquicias")
async def get_franquicias_analytics(periodo: Optional[str] = Query("historico", description="semana, mes, anio, historico")):
    try:
        respuesta = supabase.table("solicitudes_franquicia").select("*").execute()
        solicitudes = respuesta.data
        
        ciudades_count = {}
        
        for s in solicitudes:
            date_col = s.get("fecha_creacion") or s.get("created_at")
            if is_within_period(date_col, periodo):
                ciudad = s.get("ciudad")
                if ciudad:
                    ciudad_clean = ciudad.strip().title()
                    ciudades_count[ciudad_clean] = ciudades_count.get(ciudad_clean, 0) + 1
                    
        resultado = [{"ciudad": k, "cantidad": v} for k, v in ciudades_count.items()]
        resultado.sort(key=lambda x: x["cantidad"], reverse=True)
        
        return resultado
    except Exception as e:
        print("Error analytics franquicias:", e)
        raise HTTPException(status_code=500, detail="Error interno.")

@router.get("/domicilios")
async def get_domicilios_analytics(periodo: Optional[str] = Query("historico", description="semana, mes, anio, historico")):
    try:
        respuesta = supabase.table("registros_domicilios").select("*").execute()
        registros = respuesta.data
        
        sedes_count = {}
        
        for r in registros:
            date_col = r.get("fecha") or r.get("created_at") or r.get("fecha_creacion")
            if is_within_period(date_col, periodo):
                sede = r.get("nombre_sede")
                if sede:
                    sedes_count[sede] = sedes_count.get(sede, 0) + 1
                    
        resultado = [{"sede": k, "recomendaciones": v} for k, v in sedes_count.items()]
        resultado.sort(key=lambda x: x["recomendaciones"], reverse=True)
        
        return resultado
    except Exception as e:
        print("Error analytics domicilios:", e)
        raise HTTPException(status_code=500, detail="Error interno.")
