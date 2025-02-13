from aiogram import Router, types
from aiogram.fsm.context import FSMContext
#from app.states import 
from app.keyboards.inline import controller_menu, cancel_button_controller
from app import db

router = Router()

async def show_controller_menu(event):
    if isinstance(event, types.Message):
        await event.answer(
            "Меню контроллера ОТК:",
            reply_markup=controller_menu()
        )
    elif isinstance(event, types.CallbackQuery):
        await event.message.edit_text(
            "Меню контроллера ОТК:",
            reply_markup=controller_menu()
        )

async def new_controller_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Меню контроллера ОТК:",
        reply_markup=controller_menu()
    )

@router.callback_query(lambda c: c.data == "controller_data")
async def show_controller_data(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async with db.execute(
        """SELECT name, job
        FROM employees 
        WHERE tg_id = ?""",
        (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
    
    if user_data:
        name, job = user_data
        await callback.message.edit_text(
            f"Ваши данные:\n\n"
            f"Имя: {name}\n"
            f"Должность: {job}"
        )
        await new_controller_menu(callback)
    else:
        await callback.message.edit_text(
            "Данные не найдены. Обратитесь к менеджеру."
        )
        await new_controller_menu(callback)
    await callback.answer()
