from aiogram import Router, types
from aiogram.filters import Command
from app.keyboards.inline import role_keyboard, cancel_button_trunk
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.states import RegistrationStates, RemakeRequest
from app.handlers import seamstress, cutter, controller, manager
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

@router.callback_query(lambda c: c.data.startswith('role_'))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_')[1]
    await state.update_data(job=role)
    await state.set_state(RegistrationStates.waiting_for_name)
    await callback.message.answer("Введите ваше полное имя:")
    await callback.answer()

@router.message(RegistrationStates.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    try:
        data = await state.get_data()

        async with db.execute(
            """INSERT INTO employees (name, job, tg_id)
            VALUES (?, ?, ?)""",
            (data['name'], data['job'], message.from_user.id)
        ) as cursor:
            await db.fetchall(cursor)
        
        if data['job'] == 'manager':
            await manager.show_manager_menu(message)
        elif data['job'] == 'seamstress':
            await seamstress.show_seamstress_menu(message)
        elif data['job'] == 'cutter':
            await cutter.show_cutter_menu(message)
        elif data['job'] == 'controller':
            await controller.show_controller_menu(message)
        
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка регистрации: {str(e)}")
        await state.clear()

async def get_menu_function(job: str):
    menu_functions = {
        'manager': manager.show_manager_menu,
        'seamstress': seamstress.show_seamstress_menu,
        'cutter': cutter.show_cutter_menu,
        'controller': controller.show_controller_menu
    }
    return menu_functions.get(job, manager.show_manager_menu)

@router.callback_query(lambda c: c.data == "repair")
async def request_remake(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        async with db.execute(
            "SELECT job FROM employees WHERE tg_id = ?",
            (callback.from_user.id,)
        ) as cursor:
            job_data = await cursor.fetchone()
        
        if not job_data:
            await callback.message.answer("Ошибка: пользователь не найден")
            return

        show_menu_func = await get_menu_function(job_data[0])
        await state.update_data(show_menu_func=show_menu_func)
        
        await callback.message.answer(
            "Введите название оборудования, требующего ремонта:",
            reply_markup=cancel_button_trunk()
        )
        await state.set_state(RemakeRequest.waiting_for_equipment)
        
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
        if job_data:
            show_menu_func = await get_menu_function(job_data[0])
            await show_menu_func(callback)

@router.message(RemakeRequest.waiting_for_equipment)
async def process_equipment_name(message: types.Message, state: FSMContext):
    await state.update_data(equipment=message.text)
    await state.set_state(RemakeRequest.waiting_for_description)
    await message.answer(
        "Опишите проблему с оборудованием:",
        reply_markup=cancel_button_trunk()
    )

@router.message(RemakeRequest.waiting_for_description)
async def process_remake_description(message: types.Message, state: FSMContext):        
    data = await state.get_data()
    try:
        async with db.execute(
            """INSERT INTO remakes 
            (equipment_nm, description, applicant_id, remake_status, request_dttm)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (data['equipment'], message.text, message.from_user.id, 'создана')
        ) as cursor:
            await db.fetchall(cursor)
            
        await message.answer("✅ Заявка на ремонт создана!")
        await data['show_menu_func'](message)
        await state.clear()
        
    except Exception as e:
        await message.answer(f"Ошибка при создании заявки: {str(e)}")
        if 'show_menu_func' in data:
            await data['show_menu_func'](message)
        await state.clear()

@router.callback_query(lambda c: c.data == 'cancel_trunk')
async def cancel_trunk_actions(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Действие отменено")
    
    if 'show_menu_func' in data:
        await data['show_menu_func'](callback)
        
    await callback.answer()