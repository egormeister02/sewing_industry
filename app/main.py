from quart import Quart, request, jsonify
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import logging
from app.handlers import manager, seamstress, cutter, controller, trunk
from app.database import init_db, db
from app.credentials import WEBHOOK_URL, MANAGERS_ID
from app.bot import bot
from app.services import GoogleSheetsManager
# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Quart(__name__)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация обработчиков
dp.include_router(trunk.router)
dp.include_router(manager.router)
dp.include_router(seamstress.router)
dp.include_router(cutter.router)
dp.include_router(controller.router)

# Вместо прямого вызова db.connect()
async def update_managers_in_db():
    try:
        async with db.get_connection() as conn:
            for manager_id in MANAGERS_ID:
                try:
                    async with db.execute(
                        """INSERT OR REPLACE INTO employees (tg_id, job, name, status) 
                        VALUES (?, 'manager', 'Менеджер', 'appoved')""",
                        (manager_id,)
                    ) as cursor:
                        logger.info(f"Менеджер {manager_id} добавлен/обновлен")
                except Exception as e:
                    logger.error(f"Ошибка для менеджера {manager_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise
    finally:
        await db.close()

@app.before_serving
async def startup():
    logger.info("Инициализация БД")
    await init_db()
    
    logger.info("Обновление менеджеров")
    await update_managers_in_db()
    
    logger.info("Настройка вебхука")
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")

    logger.info("Настройка Google Sheets")
    sheets = GoogleSheetsManager()
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") as cursor:
        tables = [row[0] for row in await cursor.fetchall()]
        for table in tables:
            await sheets.initialize_sheet(table)
    await sheets.full_sync()

@app.route('/webhook', methods=['POST'])
async def webhook_handler():
    try:
        update = types.Update(**await request.get_json())
        asyncio.create_task(dp.feed_update(bot, update))  # Обработка в фоне
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    config.loglevel = "info"

    async def run():
        await startup()
        await serve(app, config)
    
    try:
        asyncio.run(run())
    except Exception as e:
        logger.error(f"Ошибка запуска: {str(e)}")