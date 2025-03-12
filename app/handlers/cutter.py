from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from io import BytesIO
from app.states import CutterStates
from app.keyboards.inline import cutter_menu, cancel_button_cutter, back_cancel_keyboard
from app.services import generate_qr_code
from app.handlers.trunk import delete_message_reply_markup
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
    else:
        await callback.message.edit_text(
            "Данные не найдены. Обратитесь к менеджеру.",
        )
    await callback.answer()
    await new_cutter_menu(callback)


@router.callback_query(lambda c: c.data == 'cutter_create_batch')
async def create_batch_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CutterStates.waiting_for_project_name)
    await callback.message.edit_text(
        "Введите название проекта:",
        reply_markup=cancel_button_cutter()
    )

# Обработчик кнопки "Назад"
@router.callback_query(lambda c: c.data == 'cutter_back_step')
async def go_back_step(callback: types.CallbackQuery, state: FSMContext):
    # Получаем текущее состояние
    current_state = await state.get_state()
    # Возвращаем на предыдущий шаг в зависимости от текущего состояния
    if current_state == CutterStates.waiting_for_product_name:
        await callback.message.edit_text(
            "Введите название проекта:",
            reply_markup=cancel_button_cutter()
        )
        await state.set_state(CutterStates.waiting_for_project_name)

    elif current_state == CutterStates.waiting_for_color:
        await callback.message.edit_text(
            "Введите название изделия:",
            reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
        )
        await state.set_state(CutterStates.waiting_for_product_name)

    elif current_state == CutterStates.waiting_for_size:
        await callback.message.edit_text(
            "Введите цвет изделия:",
            reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
        )
        await state.set_state(CutterStates.waiting_for_color)

    elif current_state == CutterStates.waiting_for_quantity:
        await callback.message.edit_text(
            "Введите размер изделия:",
            reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
        )
        await state.set_state(CutterStates.waiting_for_size)

    elif current_state == CutterStates.waiting_for_parts_count:
        await callback.message.edit_text(
            "Введите количество изделий в пачке:",
            reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
        )
        await state.set_state(CutterStates.waiting_for_quantity)

    else:
        await show_cutter_menu(callback)

@router.message(CutterStates.waiting_for_project_name)
async def process_project_name(message: types.Message, state: FSMContext):
    try:
        await delete_message_reply_markup(message)
    except Exception as e:
        print(f"Ошибка при удалении клавиатуры: {str(e)}")

    await state.update_data(project_name=message.text)
    await state.set_state(CutterStates.waiting_for_product_name)
    try:
        await message.answer(
            "Введите название изделия:",
            reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
        )
    except Exception as e:
        await message.answer(
            "Произошла ошибка. Попробуйте еще раз:",
            reply_markup=cancel_button_cutter()
        )
        await state.set_state(CutterStates.waiting_for_project_name)

@router.message(CutterStates.waiting_for_product_name)
async def process_product_name(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(product_name=message.text)
    await state.set_state(CutterStates.waiting_for_color)
    await message.answer("Введите цвет изделия:",
        reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
    )

@router.message(CutterStates.waiting_for_color)
async def process_color(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(color=message.text)
    await state.set_state(CutterStates.waiting_for_size)
    await message.answer("Введите размер изделия:",
        reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
    )

@router.message(CutterStates.waiting_for_size)
async def process_size(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(size=message.text)
    await state.set_state(CutterStates.waiting_for_quantity)
    await message.answer("Введите количество изделий в пачке:",
        reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
    )

@router.message(CutterStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    try:
        quantity = int(message.text)
        await state.update_data(quantity=quantity)
        await state.set_state(CutterStates.waiting_for_parts_count)
        await message.answer("Введите количество деталей в одном изделии:",
        reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
    )
    except ValueError:
        await message.answer("Пожалуйста, введите целое число:",
        reply_markup=back_cancel_keyboard("cutter_back_step", "cancel_cutter")
    )

@router.message(CutterStates.waiting_for_parts_count)
async def process_parts_count(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    try:
        parts_count = int(message.text)
        data = await state.get_data()
        
        # Устанавливаем тип пачки по умолчанию в 'обычная'
        batch_type = 'обычная'
        
        # Сохраняем данные в БД
        async with db.execute(
            """INSERT INTO batches \
            (project_nm, product_nm, color, size, quantity, parts_count, cutter_id, status, type)\
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\
            RETURNING batch_id""",
            (data['project_name'], data['product_name'], data['color'], \
             data['size'], data['quantity'], parts_count, message.from_user.id, 'создана', batch_type)
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
            filename=f'batch_{batch_id}_qr.pdf'
        )
        
        # Отправляем PDF файл пользователю
        await message.answer_document(
            document=qr_input_file,
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

@router.callback_query(lambda c: c.data == 'cutter_payments')
async def show_cutter_payments(callback: types.CallbackQuery):
    user_id = callback.from_user.id;
    
    # Получаем все выплаты для данного пользователя
    async with db.execute(
        "SELECT amount, payment_date FROM payments WHERE employee_id = ?",
        (user_id,)
    ) as cursor:
        payments = await cursor.fetchall();
    
    # Получаем сумму предстоящих выплат из представления
    async with db.execute(
        "SELECT total_payments, total_pay FROM employee_payment_info WHERE tg_id = ?",
        (user_id,)
    ) as cursor:
        payment_info = await cursor.fetchone();
    total_payments = payment_info['total_payments'] if payment_info else 0;
    total_pay = payment_info['total_pay'] if payment_info else 0;

    # Формируем сообщение с выплатами
    payment_details = "\n".join(
        [f"Сумма: {payment['amount']} | Дата: {payment['payment_date']}" for payment in payments]
    ) if payments else "Нет выплат.";

    response_message = (
        f"Ваши выплаты:\n{payment_details}\n\n"
        f"Сумма предстоящих выплат: {total_pay - total_payments}"
    );

    await callback.message.edit_text(response_message)
    await callback.answer()
    await new_cutter_menu(callback)

