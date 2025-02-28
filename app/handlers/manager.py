from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from io import BytesIO
from app.states import ManagerStates
from app.keyboards.inline import manager_menu, manager_batch_decision, cancel_button_manager, tables_selector, table_actions, back_cancel_keyboard, controller_batch_decision, seamstress_menu
from app.database import db
from app.services import generate_qr_code
from app.services.qr_processing import process_qr_code
from app.handlers.trunk import delete_message_reply_markup
from app.services.update_from_sheets import sync_db_to_sheets
from app.bot import bot
import logging
import traceback
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

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
    await callback.answer()
    await callback.message.answer(
        "Меню менеджера:",
        reply_markup=manager_menu()
    )


@router.callback_query(lambda c: c.data == 'cancel_manager')
async def cancel_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "Действие отменено",
        reply_markup=manager_menu()
    )


@router.callback_query(lambda c: c.data.startswith('change_google_sheet_'))
async def process_sync_db_to_sheets(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик для кнопки 'Внести изменения' в клавиатуре google_sheet"""
    # Извлекаем название таблицы из callback_data
    table_name = callback.data.replace('change_google_sheet_', '')
    
    await callback.answer("Начинаю синхронизацию базы данных с Google Sheets...")
    
    try:
        await sync_db_to_sheets(table_name)
        await callback.message.edit_text(
            f"✅ Синхронизация таблицы '{table_name}' с Google Sheets успешно выполнена!",
            reply_markup=manager_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {str(e)}")
        await callback.message.edit_text(
            f"❌ Ошибка при синхронизации таблицы '{table_name}': {str(e)}",
            reply_markup=manager_menu()
        )


@router.callback_query(lambda c: c.data.startswith('rollback_google_sheet_'))
async def process_sync_data_to_sheet(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик для кнопки 'Откатить' в клавиатуре google_sheet"""
    # Извлекаем название таблицы из callback_data
    table_name = callback.data.replace('rollback_google_sheet_', '')
    
    await callback.answer("Начинаю откат изменений в Google Sheets...")
    
    try:
        # Импортируем функцию внутри обработчика, чтобы избежать циклических импортов
        
        # Синхронизируем данные из БД в таблицу
        await db.sheets.sync_data_to_sheet(table_name)
        
        await callback.message.edit_text(
            f"✅ Откат изменений для таблицы '{table_name}' успешно выполнен!",
            reply_markup=manager_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка отката изменений: {str(e)}")
        await callback.message.edit_text(
            f"❌ Ошибка при откате изменений для таблицы '{table_name}': {str(e)}",
            reply_markup=manager_menu()
        )

@router.callback_query(lambda c: c.data == 'ignore_google_sheet')
async def ignore_google_sheet(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "Меню менеджера:",
        reply_markup=manager_menu()
    )

@router.callback_query(lambda c: c.data == 'manager_data')
async def show_data_tables(callback: types.CallbackQuery):
    """Обработчик для кнопки 'Данные' в меню менеджера"""
    await callback.answer()
    await callback.message.edit_text(
        "Выберите таблицу для работы с данными:",
        reply_markup=tables_selector()
    )

@router.callback_query(lambda c: c.data.startswith('select_table_'))
async def handle_table_selection(callback: types.CallbackQuery):
    """Обработчик выбора таблицы"""
    table_name = callback.data.replace('select_table_', '')
    
    await callback.answer()
    await callback.message.edit_text(
        f"Выберите действие с таблицей:",
        reply_markup=table_actions(table_name)
    )

@router.callback_query(lambda c: c.data == 'back_to_tables_selection')
async def back_to_tables(callback: types.CallbackQuery):
    """Возврат к выбору таблицы"""
    await callback.answer()
    await show_data_tables(callback)

@router.callback_query(lambda c: c.data == 'back_to_manager_menu')
async def back_to_menu(callback: types.CallbackQuery):
    """Возврат в главное меню менеджера"""
    await callback.answer()
    await show_manager_menu(callback)

@router.callback_query(lambda c: c.data.startswith('sync_db_to_sheets_'))
async def start_sync_db_to_sheets(callback: types.CallbackQuery):
    """Обработчик для синхронизации БД с Google Sheets"""
    # Извлекаем название таблицы из callback_data
    table_name = callback.data.replace('sync_db_to_sheets_', '')
    
    await callback.answer("Начинаю синхронизацию базы данных с Google Sheets...")
    
    try:
        await sync_db_to_sheets(table_name)
        await callback.message.edit_text(
            f"✅ Синхронизация таблицы '{table_name}' с Google Sheets успешно выполнена!",
            reply_markup=manager_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации БД с Google Sheets: {str(e)}")
        await callback.message.edit_text(
            f"❌ Ошибка при синхронизации таблицы '{table_name}': {str(e)}",
            reply_markup=manager_menu()
        )

@router.callback_query(lambda c: c.data.startswith('sync_data_to_sheet_'))
async def start_sync_data_to_sheet(callback: types.CallbackQuery):
    """Обработчик для синхронизации Google Sheets с БД"""
    # Извлекаем название таблицы из callback_data
    table_name = callback.data.replace('sync_data_to_sheet_', '')
    
    await callback.answer("Начинаю синхронизацию Google Sheets с базой данных...")
    
    try:
        await db.sheets.sync_data_to_sheet(table_name)
        await callback.message.edit_text(
            f"✅ Синхронизация Google Sheets с таблицей '{table_name}' успешно выполнена!",
            reply_markup=manager_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации Google Sheets с БД: {str(e)}")
        await callback.message.edit_text(
            f"❌ Ошибка при синхронизации Google Sheets с таблицей '{table_name}': {str(e)}",
            reply_markup=manager_menu()
        )

@router.callback_query(lambda c: c.data == 'manager_create_batch')
async def start_create_batch(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса создания пачки"""
    await state.set_state(ManagerStates.waiting_for_batch_type)
    await callback.answer()
    await callback.message.edit_text(
        "Введите тип пачки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Обычная", callback_data="batch_type_обычная"),
             InlineKeyboardButton(text="Образец", callback_data="batch_type_образец")]
        ])
    )

@router.callback_query(lambda c: c.data.startswith('batch_type_'))
async def process_batch_type_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора типа пачки"""
    batch_type = callback.data.split('_')[2]  # Получаем тип пачки из callback_data
    await state.update_data(batch_type=batch_type)
    await callback.answer()
    await callback.message.edit_text(
        "Введите название проекта:",
        reply_markup=cancel_button_manager()
    )
    await state.set_state(ManagerStates.waiting_for_project_name)

@router.message(ManagerStates.waiting_for_project_name)
async def manager_process_project_name(message: types.Message, state: FSMContext):
    try:
        await delete_message_reply_markup(message)
    except Exception as e:
        print(f"Ошибка при удалении клавиатуры: {str(e)}")

    await state.update_data(project_name=message.text)
    await state.set_state(ManagerStates.waiting_for_product_name)
    try:
        await message.answer(
            "Введите название изделия:",
            reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
        )
    except Exception as e:
        await message.answer(
            "Произошла ошибка. Попробуйте еще раз:",
            reply_markup=cancel_button_manager()
        )
        await state.set_state(ManagerStates.waiting_for_project_name)

@router.message(ManagerStates.waiting_for_product_name)
async def manager_process_product_name(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(product_name=message.text)
    await state.set_state(ManagerStates.waiting_for_color)
    await message.answer("Введите цвет изделия:",
        reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
    )

@router.message(ManagerStates.waiting_for_color)
async def manager_process_color(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(color=message.text)
    await state.set_state(ManagerStates.waiting_for_size)
    await message.answer("Введите размер изделия:",
        reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
    )

@router.message(ManagerStates.waiting_for_size)
async def manager_process_size(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    await state.update_data(size=message.text)
    await state.set_state(ManagerStates.waiting_for_quantity)
    await message.answer("Введите количество изделий в пачке:",
        reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
    )

@router.message(ManagerStates.waiting_for_quantity)
async def manager_process_quantity(message: types.Message, state: FSMContext):
    await delete_message_reply_markup(message)
    try:
        quantity = int(message.text)
        await state.update_data(quantity=quantity)
        data = await state.get_data()
        await state.set_state(ManagerStates.waiting_for_parts_count)
        await message.answer("Введите количество деталей в одном изделии:",
        reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
    )
    except ValueError:
        await message.answer("Пожалуйста, введите целое число:",
        reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
    )

@router.message(ManagerStates.waiting_for_parts_count)
async def process_parts_count(message: types.Message, state: FSMContext):
    """Обработка ввода количества деталей в пачке и создание пачки в БД"""
    try:
        parts_count = int(message.text)
        data = await state.get_data()
        
        # Сохраняем данные в БД
        async with db.execute(
            """INSERT INTO batches \
            (project_nm, product_nm, color, size, quantity, parts_count, cutter_id, status, type)\
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\
            RETURNING batch_id""",
            (data['project_name'], data['product_name'], data['color'], \
             data['size'], data['quantity'], parts_count, message.from_user.id, 'создана', data['batch_type'])
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
        
        # Отправляем QR-код пользователю
        file_object = BytesIO(qr_image)
        qr_input_file = BufferedInputFile(
            file_object.getvalue(), 
            filename=f'batch_{batch_id}_qr.png'
        )
        
        await message.answer_photo(
            photo=qr_input_file,
            caption=f"✅ Пачка #{batch_id} создана!\nQR-код для работы:"
        )
        await message.answer(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )
        await state.clear()
        
    except ValueError as e:
        await message.answer(f"Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating batch: {str(e)}")
        await message.answer(f"Ошибка создания пачки: {str(e)}")
        await state.clear()
        await message.answer(
            "Меню менеджера:",
            reply_markup=manager_menu()
        )

@router.callback_query(lambda c: c.data == 'manager_back_step')
async def manager_go_back_step(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' для менеджера при создании пачки"""
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == ManagerStates.waiting_for_product_name.state:
        # Возврат к вводу названия проекта
        await state.set_state(ManagerStates.waiting_for_project_name)
        await callback.answer()
        await callback.message.edit_text(
            "Введите название проекта:",
            reply_markup=cancel_button_manager()
        )
    elif current_state == ManagerStates.waiting_for_color.state:
        # Возврат к вводу названия изделия
        await state.set_state(ManagerStates.waiting_for_product_name)
        await callback.answer()
        await callback.message.edit_text(
            "Введите название изделия:",
            reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
        )
    elif current_state == ManagerStates.waiting_for_size.state:
        # Возврат к вводу цвета изделия
        await state.set_state(ManagerStates.waiting_for_color)
        await callback.answer()
        await callback.message.edit_text(
            "Введите цвет изделия:",
            reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
        )
    elif current_state == ManagerStates.waiting_for_quantity.state:
        # Возврат к вводу размера изделия
        await state.set_state(ManagerStates.waiting_for_size)
        await callback.answer()
        await callback.message.edit_text(
            "Введите размер изделия:",
            reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
        )
    elif current_state == ManagerStates.waiting_for_qr.state:
        # Возврат в меню менеджера
        await state.clear()
        await callback.answer()
        await callback.message.edit_text(
            "Проверка пачки отменена",
            reply_markup=manager_menu()
        )
    else:
        # Если состояние не определено, просто отменяем операцию
        await state.clear()
        await callback.answer()
        await callback.message.edit_text(
            "Операция отменена",
            reply_markup=manager_menu()
        )
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "manager_check_batch")
async def start_check_batch(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса проверки пачки"""
    await state.set_state(ManagerStates.waiting_for_qr)
    await callback.answer()
    await callback.message.edit_text(
        "Пожалуйста, отправьте фото QR-кода пачки",
        reply_markup=cancel_button_manager()
    )

@router.message(ManagerStates.waiting_for_qr, F.photo)
async def process_batch_qr_photo(message: types.Message, state: FSMContext):
    """Обработка фотографии QR-кода пачки"""
    try:
        # Получаем фотографию с наивысшим разрешением
        # Заменяем проблемную строку с json-сериализацией
        logger.debug("Received message: %s", message.model_dump_json())
        
        # Проверяем вложение фото
        if message.photo:
            photo = message.photo[-1]
        elif message.document and message.document.mime_type.startswith('image/'):
            photo = message.document
        else:
            await message.answer("❌ Отправьте изображение как фото!")
            return
        
        file = await message.bot.get_file(photo.file_id)
        image_data = await message.bot.download_file(file.file_path)

        try:
            qr_text = await process_qr_code(image_data.read())
            print(f"Decoded QR: {qr_text}")
        except Exception as decode_error:
            await message.answer("❌ Не удалось прочитать QR-код. Убедитесь что:")
            await message.answer("- Фото хорошо освещено\n- QR-код в фокусе\n- Нет бликов")
            raise decode_error
        
        batch_id = int(qr_text.split('ID:')[1].split('\n')[0].strip())
        
        if batch_id:
            # Если QR-код успешно прочитан
            await process_batch_id(message, state, batch_id)
        else:
            # Если QR-код не прочитан
            await message.answer(
                "Не удалось распознать QR-код. Пожалуйста, отправьте более четкое изображение или введите ID пачки вручную.",
                reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
            )
    except Exception as e:
        logger.error(f"Error processing QR code: {e}")
        await message.answer(
            "Произошла ошибка при обработке QR-кода. Пожалуйста, попробуйте еще раз или введите ID пачки вручную.",
            reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
        )

@router.message(ManagerStates.waiting_for_qr, F.text)
async def process_batch_id_text(message: types.Message, state: FSMContext):
    """Обработка текстового ID пачки"""
    batch_id = message.text.strip()
    await process_batch_id(message, state, batch_id)

async def process_batch_id(message: types.Message, state: FSMContext, batch_id: str):
    """Обработка ID пачки и отображение информации о пачке"""
    try:
        # Получаем информацию о пачке из базы данных
        async with db.execute(
            """
            SELECT b.batch_id as id, b.project_nm as project_name, b.product_nm as product_name, \
                   b.color, b.size, b.quantity, b.seamstress_id, b.parts_count,
                   b.status, b.created_at, b.type,
                   c.name as cutter_name
            FROM batches b
            LEFT JOIN employees c ON b.cutter_id = c.tg_id
            WHERE b.batch_id = ?
            """,
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()

        if not batch_data:
            await message.answer("❌ Пачка не найдена")
            await state.clear()
            await show_manager_menu(message)
            return
        
        elif batch_data[8] == 'шьется' or batch_data[8] == 'создана' or batch_data[8] == 'переделка начата':
            await message.answer("❌ Пачка еще не пошита")
            await state.clear()
            await show_manager_menu(message)
            return
        elif batch_data[8] == 'пошита' or batch_data[8] == 'переделка завершена':

            await state.update_data(batch_data=batch_data)
            await state.set_state(ManagerStates.confirm_batch)

            # Формируем сообщение с информацией о пачке
            batch_info = (
                f"📦 <b>Информация о пачке #{batch_data['id']}</b>\n\n"
                f"🏷 Проект: {batch_data['project_name']}\n"
                f"👕 Изделие: {batch_data['product_name']}\n"
                f"🎨 Цвет: {batch_data['color']}\n"
                f"📏 Размер: {batch_data['size']}\n"
                f"🔢 Количество: {batch_data['quantity']}\n"
                f"📊 Количество деталей: {batch_data['parts_count']}\n"
                f"👤 Раскройщик: {batch_data['cutter_name'] or 'Не указан'}\n"
                f"📅 Создана: {batch_data['created_at']}\n"
                f"📊 Статус: {batch_data['status']}\n"
                f"🔄 Тип: {batch_data['type']}"
            )

            # Отправляем информацию о пачке
            await message.answer(batch_info, parse_mode="HTML")
            
            await message.answer("Проверка пачки завершена", reply_markup=manager_batch_decision())
        else:
            # Если пачка не найдена
            await message.answer(
                f"Пачка с ID '{batch_id}' не найдена. Пожалуйста, проверьте ID и попробуйте снова.",
                reply_markup=back_cancel_keyboard("manager_back_step", "cancel_manager")
            )
    except Exception as e:
        logger.error("QR processing failed: %s", traceback.format_exc())
        await message.answer("❌ Ошибка обработки QR-кода. Попробуйте еще раз!", reply_markup=cancel_button_manager())
        await state.set_state(ManagerStates.waiting_for_qr)

@router.callback_query(ManagerStates.confirm_batch)
async def handle_batch_decision(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        batch_id = data.get('batch_data')[0]
        seamstress_id = data.get('batch_data')[6]
        user_id = callback.from_user.id
        msg = "Действие отменено"
        
        if not batch_id:
            await callback.answer("❌ Ошибка: пачка не найдена")
            return

        action = callback.data.split('_')[-1]
        
        if action == "approve":
            async with db.execute(
                """UPDATE batches \
                SET status = 'готово', \
                    controller_id = ?, \
                    control_dttm = CURRENT_TIMESTAMP \
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            msg = "✅ Пачка успешно принята!"
            
        elif action == "reject":
            async with db.execute(
                """UPDATE batches \
                SET status = 'неисправимый брак', \
                    controller_id = ?, \
                    control_dttm = CURRENT_TIMESTAMP \
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            msg = "❌ Пачка помечена как брак!"
            
        elif action == "remake":
            async with db.execute(
                """UPDATE batches \
                SET status = 'брак на переделке', \
                    controller_id = ?, \
                    control_dttm = CURRENT_TIMESTAMP \
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            msg = "🔄 Пачка отправлена на переделку"

            if seamstress_id:
                await bot.send_message(
                    chat_id=seamstress_id,
                    text=f"⚠️ Пачка {batch_id} требует переделки!\n"
                         "Пожалуйста, заберите ее из зоны контроля.",
                    reply_markup=seamstress_menu()
                )
            msg = "🔄 Пачка отправлена на переделку"

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(msg)
        await state.clear()
        await new_manager_menu(callback)
    except Exception as e:
        logger.error(f"Batch decision error: {traceback.format_exc()}")
        await callback.answer("⚠️ Произошла ошибка при обработке")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data == 'manager_payments')
async def show_employee_payments(callback: types.CallbackQuery):
    # Получаем всех сотрудников (раскройщиков и швей)
    async with db.execute(
        "SELECT tg_id, name FROM employees WHERE job IN ('раскройщик', 'швея')"
    ) as cursor:
        employees = await cursor.fetchall()

    # Создаем клавиатуру с кнопками для каждого сотрудника
    buttons = [
        [InlineKeyboardButton(text=employee['name'], callback_data=f'pay_{employee["tg_id"]}')]
        for employee in employees
    ]
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="cancel_manager")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text("Выберите сотрудника для выплаты:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('pay_'))
async def process_employee_selection(callback: types.CallbackQuery, state: FSMContext):
    employee_id = int(callback.data.split('_')[1])
    await callback.message.edit_text("Введите сумму выплаты:", reply_markup=cancel_button_manager())
    
    # Сохраняем выбранного сотрудника в состоянии
    await state.update_data(employee_id=employee_id)
    await state.set_state(ManagerStates.waiting_for_payment_amount)
    await callback.answer()

@router.message(ManagerStates.waiting_for_payment_amount)
async def process_payment_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        data = await state.get_data()
        employee_id = data['employee_id']

        # Добавляем запись в таблицу payments
        async with db.execute(
            """INSERT INTO payments (employee_id, amount) VALUES (?, ?)""",
            (employee_id, amount)
        ) as cursor:
            await cursor.fetchall()

        await message.answer("✅ Выплата успешно добавлена!")
        await state.clear()
        await show_manager_menu(message)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное целое число.")
    except Exception as e:
        await message.answer(f"Ошибка при добавлении выплаты: {str(e)}")
        await state.clear()
        await show_manager_menu(message)

