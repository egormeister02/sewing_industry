from quart import Quart, request, jsonify
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
from app.handlers import manager, seamstress, cutter, controller, trunk
from app.database import init_db
from app.credentials import WEBHOOK_URL
from app.bot import bot
app = Quart(__name__)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация обработчиков
dp.include_router(trunk.router)
dp.include_router(manager.router)
dp.include_router(seamstress.router)
dp.include_router(cutter.router)
dp.include_router(controller.router)

# Инициализация БД
@app.before_serving
async def startup():
    await init_db()
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")

# Обработчик вебхука
@app.route('/webhook', methods=['POST'])
async def webhook_handler():
    if request.headers.get('content-type') == 'application/json':
        update_data = await request.get_json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'invalid content'}), 400

if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    
    async def run():
        await startup()
        await serve(app, config)
    
    asyncio.run(run())