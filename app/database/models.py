from threading import Thread
import sqlite3
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
        self.audit_thread = None
        self.sheets = GoogleSheetsManager(db_instance=self)  # Передаем текущий экземпляр БД  # Инициализируем позже


    def _start_audit_thread(self):
        def audit_worker():
            sync_conn = None
            try:
                sync_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                sync_conn.execute("PRAGMA foreign_keys = ON")
                
                def update_handler(op_type, db_name, table_name, row_id):
                    """Обработчик изменений с проверкой соединения"""
                    if not table_name.endswith('_audit'):
                        return
                    
                    try:
                        # Получаем реальный audit_id
                        cur = sync_conn.execute(
                            f"SELECT audit_id FROM {table_name} WHERE rowid = ?",
                            (row_id,)
                        )
                        audit_id = cur.fetchone()[0]
                        
                        # Запускаем обработку в отдельном потоке
                        Thread(
                            target=asyncio.run,
                            args=(self._process_audit_change(table_name, audit_id),)
                        ).start()
                        
                    except Exception as e:
                        logger.error(f"Update handler error: {str(e)}")

                # Устанавливаем хук после инициализации соединения
                sync_conn.set_update_hook(update_handler)
                
                # Бесконечный цикл с обработкой ошибок
                while True:
                    try:
                        # Поддерживаем соединение активным
                        sync_conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
                        time.sleep(1)  # Задержка для снижения нагрузки
                    except sqlite3.ProgrammingError as e:
                        logger.error(f"Connection lost: {str(e)}")
                        break
                    except Exception as e:
                        logger.error(f"Audit worker error: {str(e)}")
                        time.sleep(5)

            except Exception as e:
                logger.error(f"Audit worker failed: {str(e)}")
            finally:
                if sync_conn:
                    try:
                        sync_conn.close()
                    except Exception as e:
                        logger.error(f"Error closing connection: {str(e)}")

        self.audit_thread = Thread(target=audit_worker, daemon=True)
        self.audit_thread.start()

    async def _process_audit_change(self, table_name, row_id):
        try:
            main_table = table_name.rsplit('_audit', 1)[0]
            
            # Сначала получаем данные ДО удаления
            async with self.execute(f"SELECT * FROM {table_name}") as cursor:
                audit_rows = await self.fetchall(cursor)
                audit_ids = [row['audit_id'] for row in audit_rows]  # Получаем ID после выборки

            # Затем удаляем записи
            if audit_ids:
                async with self.execute(
                    f"DELETE FROM {table_name} WHERE audit_id IN ({','.join(['?']*len(audit_ids))})",
                    audit_ids
                ) as cursor:
                    await cursor.execute()  # Нужно явно выполнить запрос

                # Обрабатываем полученные данные
                for audit_row in audit_rows:
                    action_type = audit_row['action_type']
                    
                    if action_type == 'DELETE':
                        await self.sheets.delete_row(main_table, audit_row)
                    else:
                        await self.sheets.sync_single_row(main_table, audit_row, action_type)

        except Exception as e:
            logger.error(f"Audit processing error: {str(e)}")
            raise  # Важно пробросить исключение дальше

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
    db._start_audit_thread()
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