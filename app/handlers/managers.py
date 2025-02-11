from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.states.managers import ManagerStates
from app.keyboards.inline import manager_menu, cancel_button
from app import db

router = Router()

@router.callback_query(lambda c: c.data.startswith('role_'))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_')[1]
    
    if role == 'manager':
        await callback.message.edit_text(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )

@router.callback_query(lambda c: c.data == 'manager_create_product')
async def create_product_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerStates.waiting_for_name)
    await callback.message.edit_text(
        "Введите название образца:",
        reply_markup=cancel_button()
    )

@router.callback_query(lambda c: c.data == 'cancel')
async def cancel_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Создание отменено",
        reply_markup=manager_menu()
    )

# Обработка ввода названия
@router.message(ManagerStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ManagerStates.waiting_for_parts_number)
    await message.answer(
        "Введите номер детали:",
        reply_markup=cancel_button()
    )

@router.message(ManagerStates.waiting_for_parts_number)
async def process_parts_number(message: types.Message, state: FSMContext):
    await state.update_data(parts_number=message.text)
    await state.set_state(ManagerStates.waiting_for_product_cost)
    await message.answer(
        "Введите стоимость продукта:",
        reply_markup=cancel_button()
    )

@router.message(ManagerStates.waiting_for_product_cost)
async def process_product_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text)
        await state.update_data(product_cost=cost)
        await state.set_state(ManagerStates.waiting_for_detail_payment)
        await message.answer(
            "Введите стоимость детали:",
            reply_markup=cancel_button()
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число!")

@router.message(ManagerStates.waiting_for_detail_payment)
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