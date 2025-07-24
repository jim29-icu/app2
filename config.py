import os
from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise Exception("Error: La variable de entorno MONGO_URI no está definida.")


