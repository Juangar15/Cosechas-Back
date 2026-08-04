import math
from config import supabase
import urllib.parse
import requests

def geocode_address(query):
    """
    Usa la API de Esri (ArcGIS) World Geocoding Service para transformar una dirección en texto a Lat/Lon.
    """
    encoded_query = urllib.parse.quote(f"{query}, Colombia")
    url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&maxLocations=1&singleLine={encoded_query}"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('candidates') and len(data['candidates']) > 0:
                lon = float(data['candidates'][0]['location']['x'])
                lat = float(data['candidates'][0]['location']['y'])
                return lat, lon
    except Exception as e:
        print(f"Error geocodificando '{query}': {e}")
        
    return None, None

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

def tiene_domicilio(sede):
    celular = sede.get('pdv_celular')
    tiene_propio = bool(celular and str(celular).strip().lower() != 'no')
    
    rappi = str(sede.get('pdv_aplicacion_rappi', '')).strip().lower()
    tiene_plat = rappi in ['rappi', 'didi', 'ambos']
    
    return tiene_propio or tiene_plat

def analizar_ubicacion_sedes(lat_cliente, lon_cliente, max_dist_domicilio=10.0):
    """
    Consulta todas las sedes y devuelve:
    1. La más cercana físicamente.
    2. La más cercana con opciones de domicilio (propio o app) en un radio <= max_dist_domicilio.
    """
    try:
        respuesta = supabase.table("sedes_oficiales").select("*").eq('pdv_estado', 'OPERANDO').execute()
        sedes = respuesta.data
        
        if not sedes:
            return None, None

        sede_absoluta = None
        dist_absoluta = float('inf')
        
        sede_domicilio = None
        dist_domicilio = float('inf')

        for sede in sedes:
            if not sede.get('latitud') or not sede.get('longitud'):
                continue

            dist = calcular_distancia(lat_cliente, lon_cliente, sede['latitud'], sede['longitud'])
            
            # Sede absoluta
            if dist < dist_absoluta:
                dist_absoluta = dist
                sede_absoluta = sede
                
            # Sede con domicilio
            if dist <= max_dist_domicilio and tiene_domicilio(sede):
                if dist < dist_domicilio:
                    dist_domicilio = dist
                    sede_domicilio = sede
                    
        if sede_absoluta:
            sede_absoluta['distancia_km'] = dist_absoluta
        if sede_domicilio:
            sede_domicilio['distancia_km'] = dist_domicilio
            
        return sede_absoluta, sede_domicilio

    except Exception as e:
        print(f"Error al buscar sede cercana: {e}")
        return None, None