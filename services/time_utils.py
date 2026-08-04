import re
from datetime import datetime, time
import pytz

def parse_and_check_horario(horario_str: str) -> dict:
    """
    Analiza una cadena como 'L-S 08:00 AM - 05:00 PM - D 08:00 AM a 03:00 PM'
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

    # Extraer todos los rangos usando regex. Se captura días asegurando que inicie con letra. Y las horas opcionalmente con AM/PM
    # Modificado para tolerar guiones o puntos como separadores de minutos (Ej. 20-00 en lugar de 20:00)
    matches = re.findall(r'([LMIJVSDF][LMIJVSDF,\- ]*)\s+(\d{1,2}[:.\-]\d{2}(?:\s*[APap][Mm])?)\s*[-a]\s*(\d{1,2}[:.\-]\d{2}(?:\s*[APap][Mm])?)', horario_str.upper())
    
    is_open = False
    friendly_parts = []
    
    if not matches:
        return {"abierto_ahora": True, "mensaje_amigable": horario_str}

    day_replacements = [
        ('MI', 'Miércoles'), ('L', 'Lunes'), ('M', 'Martes'), 
        ('J', 'Jueves'), ('V', 'Viernes'), ('S', 'Sábado'), 
        ('D', 'Domingo'), ('F', 'Festivos')
    ]

    for days_str, start_time_str, end_time_str in matches:
        # Strip caracteres que sobren en los bordes
        days_str_clean = days_str.strip(' -,')
        active_days = set()
        
        # 1. Parsear los días para la lógica
        parts = [p.strip() for p in days_str_clean.replace(' ', '').split(',')]
        for part in parts:
            subtokens = part.split('-')
            if len(subtokens) == 2:
                # Rango tradicional (ej L-S)
                start_d, end_d = subtokens[0], subtokens[1]
                if start_d in dias_map and end_d in dias_map:
                    s_idx, e_idx = dias_map[start_d], dias_map[end_d]
                    if s_idx <= e_idx:
                        for i in range(s_idx, e_idx + 1): active_days.add(i)
            elif len(subtokens) >= 3:
                # Rango complejo (ej L-D-F o L-M-V)
                if subtokens[0] == 'L' and subtokens[1] in ['S', 'D'] and subtokens[-1] == 'F':
                    # Es un rango "Lunes a Sab/Dom y Festivos"
                    if 'L' in dias_map and subtokens[1] in dias_map:
                        for i in range(dias_map['L'], dias_map[subtokens[1]] + 1): active_days.add(i)
                    active_days.add(dias_map['F'])
                else:
                    # Se asumen como días sueltos (L-M-V -> Lunes, Martes y Viernes)
                    for st in subtokens:
                        if st in dias_map: active_days.add(dias_map[st])
            elif len(subtokens) == 1:
                if subtokens[0] in dias_map: active_days.add(dias_map[subtokens[0]])
        
        # 2. Parsear las horas para la lógica
        def parse_time(t_str):
            t_str = t_str.strip()
            is_pm = 'PM' in t_str
            is_am = 'AM' in t_str
            t_clean = re.sub(r'[A-Z\s]', '', t_str)
            t_clean = t_clean.replace('.', ':').replace('-', ':')
            h, m = map(int, t_clean.split(':'))
            # Ajuste de formato 24h
            if is_pm and h < 12: h += 12
            if is_am and h == 12: h = 0
            return time(h, m), h, m
            
        t_start, start_h, start_m = parse_time(start_time_str)
        t_end, end_h, end_m = parse_time(end_time_str)
        
        # Validar si está abierto hoy a esta hora
        if current_weekday in active_days:
            if t_start <= current_time <= t_end:
                is_open = True
                
        # 3. Construir mensaje amigable
        friendly_days = days_str_clean
        for code, name in day_replacements:
            # Usar delimitadores de letras para no sobreescribir partes de otras palabras
            friendly_days = re.sub(r'(?<![a-zA-ZáéíóúÁÉÍÓÚ])' + code + r'(?![a-zA-ZáéíóúÁÉÍÓÚ])', name, friendly_days)
            
        def to_12h(h, m):
            period = 'AM' if h < 12 else 'PM'
            h12 = h if 0 < h <= 12 else (12 if h == 0 else h - 12)
            return f"{h12:02d}:{m:02d} {period}"
            
        # Formatear la cadena final (e.g. Lunes a Domingo y Festivos)
        if ',' in friendly_days:
            friendly_days = friendly_days.replace('-', ' a ')
        else:
            partes = [p.strip() for p in friendly_days.split('-')]
            if len(partes) == 2:
                if partes[1].strip().lower() in ['festivos', 'festivo', 'f']:
                    friendly_days = f"{partes[0]} y {partes[1]}"
                else:
                    friendly_days = f"{partes[0]} a {partes[1]}"
            elif len(partes) >= 3:
                # Verificar si es un rango como L-D-F (termina en festivo y el anterior es domingo/sabado)
                if ("festivo" in partes[-1].lower() or "f" == partes[-1].lower()) and ("domingo" in partes[-2].lower() or "sábado" in partes[-2].lower()):
                     friendly_days = f"{partes[0]} a {partes[1]} y {partes[-1]}"
                else:
                     friendly_days = ", ".join(partes[:-1]) + f" y {partes[-1]}"
            else:
                friendly_days = friendly_days.replace('-', ' a ')
                
        friendly_parts.append(f"{friendly_days}: {to_12h(start_h, start_m)} a {to_12h(end_h, end_m)}")

    mensaje = "\n  • " + "\n  • ".join(friendly_parts) if friendly_parts else horario_str
    
    return {
        "abierto_ahora": is_open,
        "mensaje_amigable": mensaje
    }
