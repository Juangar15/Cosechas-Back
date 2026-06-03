from fastapi import Depends, HTTPException, Header
from config import supabase

def get_current_user(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido o ausente")
        
    token = authorization.replace("Bearer ", "")
    
    try:
        # Validar el token con Supabase Auth
        res_auth = supabase.auth.get_user(token)
        if not res_auth or not res_auth.user:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
            
        user = res_auth.user
        
        # Obtener el rol del usuario desde perfiles_usuarios (usando email y tolerando espacios)
        res_rol = supabase.table("perfiles_usuarios").select("rol").ilike("email", f"%{user.email.strip()}%").execute()
        
        if not res_rol.data:
            # Por defecto si no tiene rol explícito en la tabla
            rol = "sin_rol"
        else:
            rol = res_rol.data[0].get("rol", "sin_rol")
            
        return {"user": user, "rol": rol, "email": user.email}
        
    except Exception as e:
        print(f"Error autenticando token: {e}")
        raise HTTPException(status_code=401, detail="Sesión caducada o inválida")
