import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI")

client: AsyncIOMotorClient = None
db = None


async def init_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["nullspacebot"]
    print("[OK] Conectado a MongoDB", flush=True)
    return db


def get_db():
    return db
