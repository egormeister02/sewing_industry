from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.states.managers import ManagerStates, RegistrationStates
from app.keyboards.inline import manager_menu, cancel_button_manager
from app.handlers import seamstress, cutter, controller
from app import db

router = Router()

async def show_manager_menu(event):
    if isinstance(event, types.Message):
        await event.answer(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )
    elif isinstance(event, types.CallbackQuery):
        await event.message.edit_text(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )

async def new_manager_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Меню менеджера:",
        reply_markup=manager_menu()
    )

@router.callback_query(lambda c: c.data.startswith('role_'))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_')[1]
    await state.update_data(job=role)
    await state.set_state(RegistrationStates.waiting_for_name)
    await callback.message.answer("Введите ваше полное имя:")

@router.message(RegistrationStates.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RegistrationStates.waiting_for_phone)
    await message.answer("Введите ваш контактный телефон:", reply_markup=cancel_button_manager())

@router.message(RegistrationStates.waiting_for_phone)
async def process_registration_phone(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        phone = message.text
        
        async with db.execute(
            """INSERT INTO employees (name, job, phone_number, tg_id)
            VALUES (?, ?, ?, ?)""",
            (data['name'], data['job'], phone, message.from_user.id)
        ) as cursor:
            await db.fetchall(cursor)
        
        if data['job'] == 'manager':
            await show_manager_menu(message)
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

@router.callback_query(lambda c: c.data == 'manager_create_product')
async def create_product_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerStates.waiting_for_name)
    await callback.message.edit_text(
        "Введите название образца:",
        reply_markup=cancel_button_manager()
    )

@router.callback_query(lambda c: c.data == 'manager_analytics')
async def get_analytics(callback: types.CallbackQuery, state: FSMContext):
    async with db.execute("SELECT * FROM products") as cursor:
        products = await cursor.fetchall()
        
    if not products:
        current_text = callback.message.text
        new_text = "Список образцов пуст"
        if current_text != new_text:
            await callback.message.edit_text(new_text)
            await new_manager_menu(callback)
        return

    products_text = "Список образцов:\n\n"
    for product in products:
        products_text += f" Название: {product[1]}\n"
        products_text += f" Номер продукта: {product[2]}\n"
        products_text += f" Стоимость продукта: {product[3]} руб.\n" 
        products_text += f" Стоимость детали: {product[4]} руб.\n"
        products_text += "━━━━━━━━━━━━━━━━━\n"

    current_text = callback.message.text
    if current_text != products_text:
        await callback.message.edit_text(products_text)
        await new_manager_menu(callback)

@router.callback_query(lambda c: c.data == 'cancel_manager')
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
        reply_markup=cancel_button_manager()
    )

@router.message(ManagerStates.waiting_for_parts_number)
async def process_parts_number(message: types.Message, state: FSMContext):
    await state.update_data(parts_number=message.text)
    await state.set_state(ManagerStates.waiting_for_product_cost)
    await message.answer(
        "Введите стоимость продукта:",
        reply_markup=cancel_button_manager()
    )

@router.message(ManagerStates.waiting_for_product_cost)
async def process_product_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text)
        await state.update_data(product_cost=cost)
        await state.set_state(ManagerStates.waiting_for_detail_payment)
        await message.answer(
            "Введите стоимость детали:",
            reply_markup=cancel_button_manager()
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