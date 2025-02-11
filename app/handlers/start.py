from aiogram import Router, types
from aiogram.filters import Command
from app.keyboards.inline import role_keyboard
from app import db

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "Выберите вашу должность:",
        reply_markup=role_keyboard()
    )

@router.message(Command('testdb'))
async def test_db(message: types.Message):
    try:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await db.fetchall(cursor)
        await message.answer(f"Таблицы в БД: {', '.join([t[0] for t in tables])}")
    except Exception as e:
        await message.answer(f"Ошибка при работе с БД: {str(e)}")