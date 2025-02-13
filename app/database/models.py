import aiosqlite
from contextlib import asynccontextmanager
import logging
from app.credentials import DB_PATH 

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None

    @asynccontextmanager
    async def get_connection(self):
        """Асинхронный контекстный менеджер для подключения"""
        if not self.conn:
            self.conn = await aiosqlite.connect(DB_PATH)
            await self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info("Database connection opened")
        
        try:
            yield self.conn
        finally:
            # Не закрываем соединение явно, будем использовать одно подключение
            pass

    async def close(self):
        """Явное закрытие соединения"""
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")
            self.conn = None

    @asynccontextmanager
    async def execute(self, query, args=()):
        """Контекстный менеджер для выполнения запросов"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, args)
            try:
                yield cursor
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                logger.error(f"Transaction rolled back: {str(e)}")
                raise

    async def fetchall(self, cursor):
        return await cursor.fetchall()

async def init_db():
    """Инициализация структуры БД"""
    db = Database()
    try:
        async with db.get_connection() as conn:
            with open('app/schema.sql', 'r') as f:
                schema = f.read()
            await conn.executescript(schema)
            await conn.commit()
            logger.info("Database schema initialized")
    except Exception as e:
        logger.error(f"Error initializing DB: {str(e)}")
        raise
    finally:
        await db.close()