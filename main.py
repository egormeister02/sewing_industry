# main.py
import os
from quart import Quart, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties  # Импортируем DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.state import State, StatesGroup
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

class ManagerStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_parts_number = State()
    waiting_for_product_cost = State()
    waiting_for_detail_payment = State()

def manager_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отчет по выплатам", callback_data="manager_payments")],
        [InlineKeyboardButton(text="Аналитика", callback_data="manager_analytics")],
        [InlineKeyboardButton(text="Список ремонтов", callback_data="manager_remakes")],
        [InlineKeyboardButton(text="Создать образец", callback_data="manager_create_product")],
    ])

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

# Обработка выбора роли
@dp.callback_query(lambda c: c.data.startswith('role_'))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_')[1]
    
    if role == 'manager':
        await callback.message.edit_text(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )
    # Здесь можно добавить обработчики для других ролей

# Обработка команды /start
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Менеджер", callback_data="role_manager")],
        [InlineKeyboardButton(text="Швея", callback_data="role_seamstress")],
        [InlineKeyboardButton(text="Раскройщик", callback_data="role_cutter")],
        [InlineKeyboardButton(text="Контроллер ОТК", callback_data="role_controller")],
    ])
    await message.answer("Выберите вашу должность:", reply_markup=keyboard)


# Обработка создания продукта
@dp.callback_query(lambda c: c.data == 'manager_create_product')
async def create_product_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerStates.waiting_for_name)
    await callback.message.edit_text(
        "Введите название образца:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
        ])
    )

# Отмена создания продукта
@dp.callback_query(lambda c: c.data == 'cancel')
async def cancel_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Создание отменено",
        reply_markup=manager_menu()
    )

# Обработка ввода названия
@dp.message(ManagerStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ManagerStates.waiting_for_parts_number)
    await message.answer(
        "Введите номер детали:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
        ])
    )

# Обработка ввода номера детали
@dp.message(ManagerStates.waiting_for_parts_number)
async def process_parts_number(message: types.Message, state: FSMContext):
    await state.update_data(parts_number=message.text)
    await state.set_state(ManagerStates.waiting_for_product_cost)
    await message.answer(
        "Введите стоимость продукта:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
        ])
    )

# Обработка ввода стоимости
@dp.message(ManagerStates.waiting_for_product_cost)
async def process_product_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text)
        await state.update_data(product_cost=cost)
        await state.set_state(ManagerStates.waiting_for_detail_payment)
        await message.answer(
            "Введите стоимость детали:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
            ])
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число!")

# Обработка ввода стоимости детали и сохранение в БД
@dp.message(ManagerStates.waiting_for_detail_payment)
async def process_detail_payment(message: types.Message, state: FSMContext):
    try:
        payment = float(message.text)
        data = await state.get_data()
        
        # Сохраняем в БД
        async with db.execute(
            """INSERT INTO products 
            (name, parts_number, product_cost, detail_payment)
            VALUES (?, ?, ?, ?)""",
            (data['name'], data['parts_number'], data['product_cost'], payment)
        ) as cursor:
            await db.fetchall(cursor)
        
        await message.answer(
            "Образец успешно создан!",
            reply_markup=manager_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число!")
    except Exception as e:
        await message.answer(f"Ошибка при сохранении: {str(e)}")
        await state.clear()

'''
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
'''
# Команда для проверки работы БД
@dp.message(Command('testdb'))
async def test_db(message: types.Message):
    try:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await db.fetchall(cursor)
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