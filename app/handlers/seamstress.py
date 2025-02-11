from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.states.managers import RegistrationStates
from app.keyboards.inline import seamstress_menu, cancel_button_seamstress
from app import db

router = Router()


async def show_seamstress_menu(event):
    if isinstance(event, types.Message):
        await event.answer(
            "Меню швеи:",
            reply_markup=seamstress_menu()
        )
    elif isinstance(event, types.CallbackQuery):
        await event.message.edit_text(
            "Меню швеи:",
            reply_markup=seamstress_menu()
        )

async def new_seamstress_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Меню швеи:",
        reply_markup=seamstress_menu()
    )

@router.callback_query(lambda c: c.data == "seamstress_data")
async def show_seamstress_data(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async with db.execute(
        """SELECT name, job
        FROM employees 
        WHERE tg_id = ?""",
        (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
    
    if user_data:
        name, job = user_data  # Теперь распаковка корректна
        await callback.message.edit_text(
            f"Ваши данные:\n\n"
            f"Имя: {name}\n"
            f"Должность: {job}"
        )
        await new_seamstress_menu(callback)
    else:
        await callback.message.edit_text(
            "Данные не найдены. Обратитесь к менеджеру."
        )
        await new_seamstress_menu(callback)
    await callback.answer()
