import math
from config import supabase

def calcular_distancia(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia en kilómetros entre dos puntos geográficos usando la fórmula de Haversine.
    """
    R = 6371.0 # Radio de la Tierra en kilómetros

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia = R * c
    
    return round(distancia, 2)

def encontrar_sede_mas_cercana(lat_cliente, lon_cliente):
    """
    Consulta todas las sedes en Supabase y devuelve la más cercana a las coordenadas del cliente.
    """
    try:
        # Traemos todas las sedes operando de la base de datos oficial
        respuesta = supabase.table("sedes_oficiales").select("*").eq('pdv_estado', 'OPERANDO').execute()
        sedes = respuesta.data
        
        if not sedes:
            return None

        sede_cercana = None
        distancia_minima = float('inf')

        for sede in sedes:
            # Algunas sedes podrían no tener latitud y longitud todavía
            if not sede.get('latitud') or not sede.get('longitud'):
                continue

            dist = calcular_distancia(lat_cliente, lon_cliente, sede['latitud'], sede['longitud'])
            
            if dist < distancia_minima:
                distancia_minima = dist
                sede_cercana = sede
                
        if sede_cercana:
            # Le inyectamos la distancia calculada al diccionario para poder mostrarla en el mensaje
            sede_cercana['distancia_km'] = distancia_minima
            
        return sede_cercana

    except Exception as e:
        print(f"Error al buscar sede cercana: {e}")
        return None