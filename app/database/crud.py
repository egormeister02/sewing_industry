from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from app.database import Database
from app.credentials import DB_PATH

db = Database()

async def create_product(data: dict):
    async with db.execute(
        """INSERT INTO products 
        (name, parts_number, product_cost, detail_payment)
        VALUES (?, ?, ?, ?)""",
        (data['name'], data['parts_number'], data['product_cost'], data['detail_payment'])
    ) as cursor:
        return await db.fetchall(cursor)