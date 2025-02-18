import apsw
from threading import Thread
import logging
import aiosqlite
from contextlib import asynccontextmanager
from app.credentials import DB_PATH
from app.services.google_sheets import GoogleSheetsManager
import asyncio
import time

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.sheets = GoogleSheetsManager(db_instance=self)
        # УДАЛЕНО: asyncio.create_task(self._audit_polling_loop())
        self._polling_task = None  # Добавляем атрибут для хранения задачи

    async def start_polling(self):
        """Запускаем polling loop после инициализации приложения"""
        if not self._polling_task:
            self._polling_task = asyncio.create_task(self._audit_polling_loop())

    async def _audit_polling_loop(self):
        """Фоновая задача для периодической проверки аудит-таблиц"""
        while True:
            try:
                # Получаем список всех аудит-таблиц
                async with self.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name LIKE '%_audit'"
                ) as cursor:
                    audit_tables = [row['name'] for row in await self.fetchall(cursor)]

                # Проверяем каждую таблицу на наличие записей
                for table_name in audit_tables:
                    async with self.execute(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    ) as cursor:
                        count = (await self.fetchall(cursor))[0]['count']
                    
                    if count > 0:
                        await self._process_audit_change(table_name)

                await asyncio.sleep(1)  # Проверка каждые 5 секунд

            except Exception as e:
                logger.error(f"Ошибка в polling loop: {str(e)}", exc_info=True)
                await asyncio.sleep(5)

    async def _process_audit_change(self, table_name):
        try:
            main_table = table_name.rsplit('_audit', 1)[0]
            
            # Сначала получаем данные ДО удаления
            async with self.execute(f"SELECT * FROM {table_name}") as cursor:
                audit_rows = await self.fetchall(cursor)
                audit_ids = [row['audit_id'] for row in audit_rows]

            # Затем удаляем записи
            if audit_ids:
                
                async with self.execute(
                    f"DELETE FROM {table_name} WHERE audit_id IN ({','.join(['?']*len(audit_ids))})",
                    audit_ids
                ) as cursor:
                    pass
        
                # Обрабатываем полученные данные
                for audit_row in audit_rows:
                    action_type = audit_row['action_type']
                    
                    if action_type == 'DELETE':
                        await self.sheets.delete_row(main_table, audit_row)
                    else:
                        await self.sheets.sync_single_row(main_table, audit_row, action_type)

        except Exception as e:
            logger.error(f"Audit processing error: {str(e)}")
            raise

    @asynccontextmanager
    async def get_connection(self):
        """Асинхронный контекстный менеджер для подключения"""
        if not self.conn:
            self.conn = await aiosqlite.connect(DB_PATH)
            # Включаем доступ к колонкам по имени
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info("Database connection opened")
        
        try:
            yield self.conn
        finally:
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
        # Преобразуем строки в словари
        return [dict(row) for row in await cursor.fetchall()]

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
        
        # Запускаем polling после инициализации
        await db.start_polling()
        return db  # Возвращаем экземпляр базы данных
        
    except Exception as e:
        logger.error(f"Error initializing DB: {str(e)}")
        raise