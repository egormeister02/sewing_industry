from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.services import process_qr_code
from app.states import SeamstressStates
from app.keyboards.inline import seamstress_menu, cancel_button_seamstress, seamstress_batch, seamstress_batches_menu, seamstress_finish_batch
from app import db
import traceback
import logging
import os

router = Router()
logger = logging.getLogger(__name__)


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

@router.callback_query(lambda c: c.data == 'cancel_seamstress')
async def cancel_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено",
        reply_markup=seamstress_menu()
    )
    await callback.answer()

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

@router.callback_query(lambda c: c.data == 'seamstress_take_batch')
async def take_batch_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SeamstressStates.waiting_for_qr)
    await callback.message.edit_text(
        "📤 Отправьте фото QR-кода пачки или id пачки",
        reply_markup=cancel_button_seamstress()
    )
    await callback.answer()

@router.message(SeamstressStates.waiting_for_qr)
async def process_batch_qr(message: types.Message, state: FSMContext):
    try:
        logger.debug("Received message: %s", message.model_dump_json())
        batch_id = None
        
        # Проверяем текстовое сообщение с ID пачки
        if message.text and message.text.isdigit():
            batch_id = int(message.text)
        else:
            # Обрабатываем изображение QR-кода
            if message.photo:
                photo = message.photo[-1]
            elif message.document and message.document.mime_type.startswith('image/'):
                photo = message.document
            else:
                await message.answer("❌ Отправьте фото QR-кода или введите ID пачки")
                return

            file = await message.bot.get_file(photo.file_id)
            image_data = await message.bot.download_file(file.file_path)
            
            try:
                qr_text = await process_qr_code(image_data.read())
                logger.info(f"Decoded QR: {qr_text}")
                batch_id = int(qr_text)
            except Exception as decode_error:
                await message.answer("❌ Не удалось прочитать QR-код. Убедитесь что:")
                await message.answer("- Фото хорошо освещено\n- QR-код в фокусе\n- Нет бликов")
                raise decode_error

        # Поиск пачки в БД
        async with db.execute(
            """SELECT batch_id, project_nm, product_nm, color, size, quantity, parts_count, status, seamstress_id
            FROM batches 
            WHERE batch_id = ? AND (status = 'создана' or status = 'брак на переделке')""",
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()
        
        if not batch_data:
            await message.answer("❌ Пачка не найдена или уже взята в работу")
            await state.clear()
            await show_seamstress_menu(message)
            return
        
        if batch_data[7] == 'брак на переделке' and batch_data[8] != message.from_user.id:
            await message.answer("❌ Пачка на переделке не может быть взята в работу другой швеей")
            await state.clear()
            await show_seamstress_menu(message)
            return
            
        await state.update_data(batch_data=batch_data)
        await state.set_state(SeamstressStates.confirm_batch)
        
        response = (
            f"ID: {batch_data[0]}\n"
            f"Проект: {batch_data[1]}\n"
            f"Изделие: {batch_data[2]}\n"
            f"Цвет: {batch_data[3]}\n"
            f"Размер: {batch_data[4]}\n"
            f"Количество: {batch_data[5]}\n"
            f"Деталей: {batch_data[6]}\n\n"
            "Принять пачку в работу?"
        )
        if batch_data[7] == 'брак на переделке':
            response = "🔄 Это ваша пачка на переделке\n\n" + response
        await message.answer( 
            response,
            reply_markup=seamstress_batch()
        )
        
    except ValueError:
        await message.answer("❌ ID пачки должен быть целым числом")
        await state.set_state(SeamstressStates.waiting_for_qr)
    except Exception as e:
        logger.error("Processing failed: %s", traceback.format_exc())
        await message.answer("❌ Ошибка обработки. Проверьте данные и попробуйте еще раз!")
        await state.set_state(SeamstressStates.waiting_for_qr)

@router.callback_query(lambda c: c.data == 'accept_batch', SeamstressStates.confirm_batch)
async def accept_batch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        new_status = 'шьется'

        if data['batch_data'][7] == 'брак на переделке':
            new_status = 'переделка начата'
        
        async with db.execute(
            """UPDATE batches 
            SET seamstress_id = ?, status = ?, sew_start_dttm = CURRENT_TIMESTAMP
            WHERE batch_id = ?""",
            (callback.from_user.id, new_status, data['batch_data'][0])
        ):
            await callback.message.edit_text("✅ Пачка успешно принята в работу!")
            await state.clear()
            await show_seamstress_menu(callback)
            
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data == 'decline_batch', SeamstressStates.confirm_batch)
async def decline_batch(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Вы отказались от пачки")
    await show_seamstress_menu(callback)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'seamstress_batches')
async def show_seamstress_batches(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        
        # Получаем все пачки швеи
        async with db.execute(
            """SELECT batch_id, status 
            FROM batches 
            WHERE seamstress_id = ? and (batches.status = 'шьется' or batches.status = 'брак на переделке' or batches.status = 'переделка начата')""",
            (user_id,)
        ) as cursor:
            batches = await cursor.fetchall()
        
        if not batches:
            await callback.message.answer("У вас нет активных пачек")
            await callback.answer()
            await new_seamstress_menu(callback)
            return

        await callback.message.edit_text(
            "📦 Ваши активные пачки:",
            reply_markup=seamstress_batches_menu(batches)
        )
        await callback.answer()
        
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
        await callback.answer()

@router.callback_query(lambda c: c.data.startswith('seamstress_batch_'))
async def show_batch_details(callback: types.CallbackQuery, state: FSMContext):
    try:
        batch_id = int(callback.data.split('_')[-1])
        
        
        async with db.execute(
            """SELECT batches.batch_id, batches.project_nm, batches.product_nm, batches.color, batches.size, 
                    batches.quantity, batches.parts_count, batches.seamstress_id, batches.created_at, batches.status,
                    employees.name, batches.type
            FROM batches 
            JOIN employees ON batches.cutter_id = employees.tg_id
            WHERE batches.batch_id = ? """,
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()

        await state.update_data(batch_data=batch_data)
        if not batch_data:
            await callback.answer("Пачка не найдена")
            return
        
        response = (
            "🔍 Детали пачки:\n\n"
            f"ID: {batch_data[0]}\n"
            f"Проект: {batch_data[1]}\n"
            f"Изделие: {batch_data[2]}\n"
            f"Цвет: {batch_data[3]}\n"
            f"Размер: {batch_data[4]}\n"
            f"Количество: {batch_data[5]}\n"
            f"Деталей: {batch_data[6]}\n"
            f"Раскройщик: {batch_data[10]}\n"
            f"Дата создания: {batch_data[8]}\n"
            f"Статус: {batch_data[9]}\n"
            f"Тип: {batch_data[11]}\n"
        )
        if batch_data[9] == 'брак на переделке':
            response = "🔄 Пачка отправлена на переделку\n\n" + response + "\n\n📤 Отправьте QR-код или id пачки для начала работы"
            await state.set_state(SeamstressStates.waiting_for_qr)
            await callback.message.edit_text(response, reply_markup=cancel_button_seamstress())
            
        elif batch_data[9] == 'переделка начата':
            response = "🔄 Пачка на переделке\n\n" + response
            await callback.message.edit_text(response, reply_markup=seamstress_finish_batch())
        else:
            await callback.message.edit_text(
                response,
                reply_markup=seamstress_finish_batch())
        
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
        await callback.answer()
        await new_seamstress_menu(callback)

@router.callback_query(lambda c: c.data == 'seamstress_finish_batch')
async def finish_batch_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        batch_id = data.get('batch_data')[0]
        
        if not batch_id:
            await callback.answer("Ошибка: ID пачки не найден")
            return
        new_status = 'пошита'

        if data.get('batch_data')[9] == 'переделка начата':
            new_status = 'переделка завершена'

        async with db.execute(
            """UPDATE batches 
            SET status = ?, sew_end_dttm = CURRENT_TIMESTAMP 
            WHERE batch_id = ?""",
            (new_status, batch_id)
        ) as cursor:
            await db.fetchall(cursor)
            
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "✅ Пачка успешно завершена!", 
            reply_markup=None
        )
        await new_seamstress_menu(callback)
        
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
        await new_seamstress_menu(callback)
    finally:
        await callback.answer()
        await state.clear()

@router.callback_query(lambda c: c.data == 'seamstress_cancel_finish_batch')
async def cancel_finish_batch_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await new_seamstress_menu(callback)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'seamstress_ok')
async def close_batches_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()
    await new_seamstress_menu(callback)

@router.callback_query(lambda c: c.data == 'seamstress_payments')
async def show_seamstress_payments(callback: types.CallbackQuery):
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
    total_seamstress_pay = payment_info['total_pay'] if payment_info else 0;

    # Формируем сообщение с выплатами
    payment_details = "\n".join(
        [f"Сумма: {payment['amount']} | Дата: {payment['payment_date']}" for payment in payments]
    ) if payments else "Нет выплат.";

    response_message = (
        f"Ваши выплаты:\n{payment_details}\n\n"
        f"Сумма предстоящих выплат: {total_seamstress_pay - total_payments}"
    );

    await callback.message.edit_text(response_message);
    await new_seamstress_menu(callback)
    await callback.answer();