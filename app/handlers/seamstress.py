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
        "Создание отменено",
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
        "📤 Отправьте фото QR-кода пачки",
        reply_markup=cancel_button_seamstress()
    )
    await callback.answer()

@router.message(SeamstressStates.waiting_for_qr)
async def process_batch_qr(message: types.Message, state: FSMContext):
    try:
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
        
        temp_filename = f"temp_qr_{message.from_user.id}_{message.message_id}.jpg"
    
        with open(temp_filename, "wb") as f:
            f.write(image_data.getvalue())
        # Декодируем QR
        os.remove(temp_filename)
        try:
            qr_text = await process_qr_code(image_data.read())
            print(f"Decoded QR: {qr_text}")
        except Exception as decode_error:
            await message.answer("❌ Не удалось прочитать QR-код. Убедитесь что:")
            await message.answer("- Фото хорошо освещено\n- QR-код в фокусе\n- Нет бликов")
            raise decode_error
        
        batch_id = int(qr_text.split('ID:')[1].split('\n')[0].strip())
        
        # Ищем пачку в БД
        async with db.execute(
            """SELECT batch_id, project_nm, product_nm, color, size, quantity, parts_count 
            FROM batches 
            WHERE batch_id = ? AND seamstress_id IS NULL""",
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()
        
        if not batch_data:
            await message.answer("❌ Пачка не найдена или уже взята в работу")
            await state.clear()
            await show_seamstress_menu(message)
            return
            
        await state.update_data(batch_id=batch_id)
        await state.set_state(SeamstressStates.confirm_batch)
        
        # Формируем сообщение с данными
        response = (
            "🔍 Найдена пачка:\n\n"
            f"ID: {batch_data[0]}\n"
            f"Проект: {batch_data[1]}\n"
            f"Изделие: {batch_data[2]}\n"
            f"Цвет: {batch_data[3]}\n"
            f"Размер: {batch_data[4]}\n"
            f"Количество: {batch_data[5]}\n"
            f"Деталей: {batch_data[6]}\n\n"
            "Принять пачку в работу?"
        )
        
        await message.answer(
            response,
            reply_markup=seamstress_batch()
        )
        
    except Exception as e:
        logger.error("QR processing failed: %s", traceback.format_exc())
        await message.answer("❌ Ошибка обработки QR-кода. Попробуйте еще раз!")
        await state.set_state(SeamstressStates.waiting_for_qr)

@router.callback_query(lambda c: c.data == 'accept_batch', SeamstressStates.confirm_batch)
async def accept_batch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        async with db.execute(
            """UPDATE batches 
            SET seamstress_id = ?, status = 'шьется', sew_start_dttm = CURRENT_TIMESTAMP
            WHERE batch_id = ?""",
            (callback.from_user.id, data['batch_id'])
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
            """SELECT batch_id, project_nm, product_nm, status 
            FROM batches 
            WHERE seamstress_id = ? and batches.status = 'шьется'""",
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
        await state.update_data(batch_id=batch_id)
        
        async with db.execute(
            """SELECT batches.batch_id, batches.project_nm, batches.product_nm, batches.color, batches.size, 
                    batches.quantity, batches.parts_count, batches.seamstress_id, batches.created_at,
                    employees.name 
            FROM batches 
            JOIN employees ON batches.cutter_id = employees.tg_id
            WHERE batches.batch_id = ? """,
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()
        
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
            f"Раскройщик: {batch_data[9]}\n"
            f"Дата создания: {batch_data[8]}"
        )
        
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
        batch_id = data.get('batch_id')
        
        if not batch_id:
            await callback.answer("Ошибка: ID пачки не найден")
            return
            
        async with db.execute(
            """UPDATE batches 
            SET status = 'пошита', sew_end_dttm = CURRENT_TIMESTAMP 
            WHERE batch_id = ?""",
            (batch_id,)
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