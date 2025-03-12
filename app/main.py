import os
os.environ['TZ'] = 'Europe/Moscow'

from quart import Quart, request, jsonify
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import logging
from app.handlers import manager, seamstress, cutter, controller, trunk
from app.database import init_db, db
from app.credentials import WEBHOOK_URL, MANAGERS_ID
from app.bot import bot
from app.services.update_from_sheets import handle_google_sheets_update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.exceptions import TelegramAPIError
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

# Настройка планировщика
scheduler = AsyncIOScheduler()

def start_scheduler():
    # Запланировать выполнение функции full_sync каждый день в 4:00
    scheduler.add_job(
        func=lambda: asyncio.create_task(db.sheets.full_sync()),
        trigger='cron',
        hour=4,
        minute=0
    )
    scheduler.start()

# Вместо прямого вызова db.connect()
async def update_managers_in_db():
    try:
        async with db.get_connection() as conn:
            for manager_id in MANAGERS_ID:
                try:
                    async with db.execute(
                        """INSERT OR REPLACE INTO employees (tg_id, job, name, status) 
                        VALUES (?, 'менеджер', 'Менеджер', 'одобрено')""",
                        (manager_id,)
                    ) as cursor:
                        logger.info(f"Менеджер {manager_id} добавлен/обновлен")
                except Exception as e:
                    logger.error(f"Ошибка для менеджера {manager_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise
async def set_commands():
    await bot.set_my_commands(
        [
            types.BotCommand(command="/start", description="Меню")
        ]
    )
@app.before_serving
async def startup():
    db_instance = await init_db()  # Получаем инициализированный экземпляр БД
    app.db = db_instance  # Сохраняем в контексте приложения
    
    logger.info("Обновление менеджеров")
    await update_managers_in_db()
    
    logger.info("Настройка вебхука")
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")

    await set_commands()
    logger.info("Настройка Google Sheets")
    async with db.execute("""SELECT name FROM sqlite_master WHERE type='table'
                           AND name NOT LIKE 'sqlite_%' 
                           AND name NOT LIKE '%_audit'""") as cursor:
        tables = [row[0] for row in await cursor.fetchall()]
        for table in tables:
            await db.sheets.initialize_sheet(table)
    await db.sheets.full_sync()

    # Запуск планировщика
    start_scheduler()

@app.route('/webhook', methods=['POST'])
async def webhook_handler():
    try:
        data = await request.get_json()
        #logger.info(f"Получены данные: {data}")
        
        # Изменим проверку на более точную
        if 'update_id' in data:  # Это запрос от Telegram
            update = types.Update(**data)
            await dp.feed_update(bot, update)
            return jsonify({'status': 'ok'})
        else:  # Это запрос от Google Sheets
            await handle_google_sheets_update(data)
            return jsonify({'status': 'ok'})
            
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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