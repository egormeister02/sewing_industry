# main.py
import os
from quart import Quart, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties  # Импортируем DefaultBotProperties
from database import init_db, Database
import aiohttp
import asyncio
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
from credentials import BOT_TOKEN, WEBHOOK_URL, DB_PATH

app = Quart(__name__)

# Используем DefaultBotProperties для настройки parse_mode
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # Указываем parse_mode здесь
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

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

# Обработчик QR-кодов
@dp.message(lambda m: m.photo is not None)
async def handle_qr_code(message: types.Message):
    try:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}') as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    qr_data = await process_qr_code(image_data)
                    await message.answer(f"Данные QR-кода: {qr_data}")
                else:
                    await message.answer(f"Не удалось загрузить изображение. Код ошибки: {resp.status}")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

async def process_qr_code(image_data: bytes) -> str:
    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, BytesIO(image_data))
        decoded = await loop.run_in_executor(None, decode, image)
        return decoded[0].data.decode('utf-8') if decoded else "QR-код не распознан"
    except IndexError:
        return "QR-код не распознан"
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"

# Команда для проверки работы БД
@dp.message(Command('testdb'))
async def test_db(message: types.Message):
    try:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await cursor.fetchall()
        await message.answer(f"Таблицы в БД: {', '.join([t[0] for t in tables])}")
    except Exception as e:
        await message.answer(f"Ошибка при работе с БД: {str(e)}")

if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    
    async def run():
        await startup()
        await serve(app, config)
    
    asyncio.run(run())