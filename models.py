from pydantic import BaseModel
from typing import Optional

class MensajePrueba(BaseModel):
    texto: str
    celular: str = "573000000000"

class ActualizarEstado(BaseModel):
    nuevo_estado: str
    nota_resolucion: Optional[str] = None

class ActualizarEstadoFranquicia(BaseModel):
    nuevo_estado: str
    nota_resolucion: Optional[str] = None