from aiogram import Router, types
from aiogram.filters import Command
from app.services.qr_processing import process_qr_code
from app.bot import bot
from app.credentials import BOT_TOKEN
import aiohttp

router = Router()

@router.message(lambda m: m.photo is not None)
async def handle_qr_code(message: types.Message):
    """
    Обрабатывает сообщения с фотографиями (QR-кодами).
    """
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