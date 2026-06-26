import os
import sys
import time
import requests
from config import supabase

def geocode_address(address, city):
    """
    Usa la API de Esri (ArcGIS) World Geocoding Service.
    Es significativamente mejor para direcciones y nomenclaturas en Colombia
    que cualquier otro servicio gratuito.
    """
    import urllib.parse
    query = f"{address}, {city}, Colombia"
    encoded_query = urllib.parse.quote(query)
    url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&maxLocations=1&singleLine={encoded_query}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('candidates') and len(data['candidates']) > 0:
                lon = float(data['candidates'][0]['location']['x'])
                lat = float(data['candidates'][0]['location']['y'])
                return lat, lon
    except Exception as e:
        print(f"Error geocodificando '{query}': {e}")
        
    return None, None

def main():
    print("Iniciando migración de coordenadas para sedes_oficiales...")
    
    # 1. Traer todas las sedes
    try:
        res = supabase.table("sedes_oficiales").select("id, pdv_direccion, pdv_ciudad, latitud, longitud").execute()
        sedes = res.data
    except Exception as e:
        print(f"Error conectando a Supabase: {e}")
        sys.exit(1)
        
    if not sedes:
        print("No se encontraron sedes en la tabla.")
        return
        
    total_sedes = len(sedes)
    sedes_a_geocodificar = [s for s in sedes if not s.get('latitud') or not s.get('longitud')]
    
    print(f"Total sedes: {total_sedes}")
    print(f"Sedes sin coordenadas: {len(sedes_a_geocodificar)}")
    
    if len(sedes_a_geocodificar) == 0:
        print("¡Todas las sedes ya tienen coordenadas!")
        return

    actualizadas = 0
    fallidas = 0

    for i, sede in enumerate(sedes_a_geocodificar):
        id_sede = sede['id']
        direccion = sede.get('pdv_direccion')
        ciudad = sede.get('pdv_ciudad')
        
        print(f"[{i+1}/{len(sedes_a_geocodificar)}] Geocodificando: {direccion}, {ciudad}...")
        
        if not direccion or not ciudad or direccion == 'N/A' or ciudad == 'N/A':
            print(f"  -> Omitida (Falta dirección o ciudad)")
            fallidas += 1
            continue
            
        lat, lon = geocode_address(direccion, ciudad)
        
        if lat and lon:
            # Actualizar en Supabase
            try:
                supabase.table("sedes_oficiales").update({"latitud": lat, "longitud": lon}).eq("id", id_sede).execute()
                print(f"  -> Éxito: {lat}, {lon}")
                actualizadas += 1
            except Exception as e:
                print(f"  -> Error al actualizar Supabase: {e}")
                fallidas += 1
        else:
            print(f"  -> No se encontraron coordenadas.")
            fallidas += 1
            
        # Nominatim exige un retardo de al menos 1 segundo entre peticiones
        time.sleep(1.5)
        
    print("\nResumen:")
    print(f"Actualizadas: {actualizadas}")
    print(f"Fallidas: {fallidas}")
    print("Migración finalizada.")

if __name__ == '__main__':
    main()
