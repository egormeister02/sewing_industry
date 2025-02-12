from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from io import BytesIO
from app.states import CutterStates, RemakeRequest
from app.keyboards.inline import cutter_menu, cancel_button_cutter
from app.services import generate_qr_code
from app import db

router = Router()

async def show_cutter_menu(event):
    if isinstance(event, types.Message):
        await event.answer(
            "Меню раскройщика:",
            reply_markup=cutter_menu()
        )
    elif isinstance(event, types.CallbackQuery):
        await event.message.edit_text(
            "Меню раскройщика:",
            reply_markup=cutter_menu()
        )

async def new_cutter_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Меню раскройщика:",
        reply_markup=cutter_menu()
    )

@router.callback_query(lambda c: c.data == 'cancel_cutter')
async def cancel_cutter_actions(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено",
        reply_markup=cutter_menu()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "cutter_data")
async def show_cutter_data(callback: types.CallbackQuery):
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
        await new_cutter_menu(callback)
    else:
        await callback.message.edit_text(
            "Данные не найдены. Обратитесь к менеджеру."
        )
        await new_cutter_menu(callback)
    await callback.answer()


@router.callback_query(lambda c: c.data == 'cutter_create_batch')
async def create_batch_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CutterStates.waiting_for_project_name)
    await callback.message.edit_text(
        "Введите название проекта:",
        reply_markup=cancel_button_cutter()
    )
@router.message(CutterStates.waiting_for_project_name)
async def process_project_name(message: types.Message, state: FSMContext):
    await state.update_data(project_name=message.text)
    await state.set_state(CutterStates.waiting_for_product_name)
    await message.answer("Введите название изделия:",
        reply_markup=cancel_button_cutter()
    )

@router.message(CutterStates.waiting_for_product_name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(product_name=message.text)
    await state.set_state(CutterStates.waiting_for_color)
    await message.answer("Введите цвет изделия:",
        reply_markup=cancel_button_cutter()
    )

@router.message(CutterStates.waiting_for_color)
async def process_color(message: types.Message, state: FSMContext):
    await state.update_data(color=message.text)
    await state.set_state(CutterStates.waiting_for_size)
    await message.answer("Введите размер изделия:",
        reply_markup=cancel_button_cutter()
    )

@router.message(CutterStates.waiting_for_size)
async def process_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await state.set_state(CutterStates.waiting_for_quantity)
    await message.answer("Введите количество изделий в пачке:",
        reply_markup=cancel_button_cutter()
    )

@router.message(CutterStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        await state.update_data(quantity=quantity)
        await state.set_state(CutterStates.waiting_for_parts_count)
        await message.answer("Введите количество деталей в одном изделии:",
        reply_markup=cancel_button_cutter()
    )
    except ValueError:
        await message.answer("Пожалуйста, введите целое число:",
        reply_markup=cancel_button_cutter()
    )

@router.message(CutterStates.waiting_for_parts_count)
async def process_parts_count(message: types.Message, state: FSMContext):
    try:
        parts_count = int(message.text)
        data = await state.get_data()
        
        # Сохраняем данные в БД
        async with db.execute(
            """INSERT INTO batches 
            (project_nm, product_nm, color, size, quantity, parts_count, cutter_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING batch_id""",
            (data['project_name'], data['product_name'], data['color'], 
             data['size'], data['quantity'], parts_count, message.from_user.id)
        ) as cursor:
            result = await cursor.fetchone()
            if not result or not result[0]:
                raise ValueError("Не удалось получить ID созданной пачки")
            
            batch_id = result[0]

        # Генерируем QR-код
        qr_image = await generate_qr_code({
            'batch_id': batch_id,
            'project_name': data['project_name'],
            'product_name': data['product_name'],
            'color': data['color'],
            'size': data['size'],
            'quantity': data['quantity'],
            'parts_count': parts_count
        })
        
        file_object = BytesIO(qr_image)
        qr_input_file = BufferedInputFile(
            file_object.getvalue(), 
            filename=f'batch_{batch_id}_qr.png'
        )
        
        await message.answer_photo(
            photo=qr_input_file,
            caption=f"✅ Пачка #{batch_id} создана!\nQR-код для работы:"
        )
        await show_cutter_menu(message)
        await state.clear()
        
    except ValueError as e:
        await message.answer(f"Ошибка: {str(e)}")
    except Exception as e:
        await message.answer(f"Ошибка создания пачки: {str(e)}")
        await state.clear()
        await show_cutter_menu(message)


@router.callback_query(lambda c: c.data =="repair")
async def request_remake(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название оборудования, требующего ремонта:")
    await state.set_state(RemakeRequest.waiting_for_equipment)

@router.message(RemakeRequest.waiting_for_equipment)
async def process_equipment_name(message: types.Message, state: FSMContext):
    await state.update_data(equipment=message.text)
    await state.set_state(RemakeRequest.waiting_for_description)
    await message.answer(
        "Опишите проблему с оборудованием:",
        reply_markup=cancel_button_cutter()
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
        )as cursor:
            await db.fetchall(cursor)
            
        await message.answer("✅ Заявка на ремонт создана!")
        await state.clear()
        await show_cutter_menu(message)
        
    except Exception as e:
        await message.answer(f"Ошибка при создании заявки: {str(e)}")
        await state.clear()
        await show_cutter_menu(message)