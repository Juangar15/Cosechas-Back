import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Cargar las variables ocultas del archivo .env
load_dotenv()

# ==========================================
# CONEXIÓN A INFRAESTRUCTURA (DB, MAIL, META)
# ==========================================
SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")
EMAIL_USER: str = os.getenv("EMAIL_USER")
EMAIL_PASS: str = os.getenv("EMAIL_PASS")
EMAIL_JEFE: str = os.getenv("EMAIL_JEFE")
EMAIL_EXPANSION = os.getenv("EMAIL_EXPANSION")
EMAIL_COORD_SAC: str = os.getenv("EMAIL_COORD_SAC")
EMAIL_CAPACITADORA: str = os.getenv("EMAIL_CAPACITADORA")
EMAIL_SISTEMAS: str = os.getenv("EMAIL_SISTEMAS")
EMAIL_GERENCIA_JURIDICA: str = os.getenv("EMAIL_GERENCIA_JURIDICA")
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
