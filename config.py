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
SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
SMTP_USER: str = os.getenv("SMTP_USER")
SMTP_PASS: str = os.getenv("SMTP_PASS")
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN")

APP_ENV: str = os.getenv("APP_ENV", "dev") # "dev" por defecto si no se configura
R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY: str = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY: str = os.getenv("R2_SECRET_KEY")
R2_BUCKET_PUBLIC: str = os.getenv("R2_BUCKET_PUBLIC")
R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
