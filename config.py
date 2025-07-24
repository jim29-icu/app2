import os

MONGO_URI = os.getenv("MONGO_URI")

if MONGO_URI is None:
    raise Exception("Error: La variable de entorno MONGO_URI no está definida.")


