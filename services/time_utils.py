import re
from datetime import datetime, time
import pytz

def parse_and_check_horario(horario_str: str) -> dict:
    """
    Analiza una cadena como 'L-S 08:00-20:00 - D 08:00-15:00'
    Retorna un diccionario con si está abierto ahora y el mensaje formateado amigable.
    """
    if not horario_str or str(horario_str).strip() == "" or str(horario_str).lower() == "n/a":
        return {"abierto_ahora": True, "mensaje_amigable": "Horario no especificado en el sistema."}

    # Tiempo actual en Colombia
    colombia_tz = pytz.timezone('America/Bogota')
    now = datetime.now(colombia_tz)
    current_weekday = now.weekday() # 0 = Lunes, 6 = Domingo
    current_time = now.time()

    dias_map = {'L': 0, 'M': 1, 'MI': 2, 'J': 3, 'V': 4, 'S': 5, 'D': 6, 'F': 7}
    
    # Extraer todos los rangos usando regex: captura días (como L-S o L,M), y horas (como 08:00 y 20:00)
    matches = re.findall(r'([LMIJVSDF,\- ]+)\s+(\d{1,2}:\d{2})\s*[-a]\s*(\d{1,2}:\d{2})', horario_str.upper())
    
    is_open = False
    friendly_parts = []
    
    if not matches:
        return {"abierto_ahora": True, "mensaje_amigable": horario_str}

    # Para el formateo amigable de los días
    day_replacements = [
        ('MI', 'Miércoles'), ('L', 'Lunes'), ('M', 'Martes'), 
        ('J', 'Jueves'), ('V', 'Viernes'), ('S', 'Sábado'), 
        ('D', 'Domingo'), ('F', 'Festivos')
    ]

    for days_str, start_time_str, end_time_str in matches:
        days_str_clean = days_str.strip()
        active_days = set()
        
        # 1. Parsear los días para la lógica
        parts = [p.strip() for p in days_str_clean.replace(' ', '').split(',')]
        for part in parts:
            if '-' in part:
                start_d, end_d = part.split('-', 1)
                if start_d in dias_map and end_d in dias_map:
                    s_idx = dias_map[start_d]
                    e_idx = dias_map[end_d]
                    if s_idx <= e_idx:
                        for i in range(s_idx, e_idx + 1):
                            active_days.add(i)
            else:
                if part in dias_map:
                    active_days.add(dias_map[part])
        
        # 2. Parsear las horas para la lógica
        start_h, start_m = map(int, start_time_str.split(':'))
        end_h, end_m = map(int, end_time_str.split(':'))
        
        t_start = time(start_h, start_m)
        t_end = time(end_h, end_m)
        
        # Validar si está abierto hoy a esta hora
        if current_weekday in active_days:
            if t_start <= current_time <= t_end:
                is_open = True
                
        # 3. Construir mensaje amigable
        friendly_days = days_str_clean
        for code, name in day_replacements:
            friendly_days = re.sub(r'(?<![A-Z])' + code + r'(?![A-Z])', name, friendly_days)
            
        def to_12h(h, m):
            period = 'AM' if h < 12 else 'PM'
            h12 = h if 0 < h <= 12 else (12 if h == 0 else h - 12)
            return f"{h12:02d}:{m:02d} {period}"
            
        # Transformar "Lunes-Sábado" a "Lunes a Sábado"
        friendly_days = friendly_days.replace('-', ' a ')
        friendly_parts.append(f"{friendly_days}: {to_12h(start_h, start_m)} a {to_12h(end_h, end_m)}")

    mensaje = "\n  • " + "\n  • ".join(friendly_parts) if friendly_parts else horario_str
    
    return {
        "abierto_ahora": is_open,
        "mensaje_amigable": mensaje
    }
