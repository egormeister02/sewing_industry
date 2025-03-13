from aiogram import Router, types
from aiogram.fsm.context import FSMContext
import traceback
import logging
from app.states import ControllerStates
from app.keyboards.inline import controller_menu, cancel_button_controller, controller_batch_decision, seamstress_menu
from app import bot
from app import db
from app.services.qr_processing import process_qr_code

logger = logging.getLogger(__name__)

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

@router.callback_query(lambda c: c.data == 'controller_take_batch')
async def take_batch_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ControllerStates.waiting_for_qr)
    await callback.message.edit_text(
        "📤 Отправьте фото QR-кода пачки",
        reply_markup=cancel_button_controller()
    )
    await callback.answer()

@router.message(ControllerStates.waiting_for_qr)
async def process_batch_qr(message: types.Message, state: FSMContext):
    try:
        qr_text = "Не распознан"
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
        
        # Читаем данные напрямую как bytes
        image_bytes = image_data.getvalue()  
        
        # Декодируем QR
        try:
            qr_text = await process_qr_code(image_bytes)
            print(f"Decoded QR: {qr_text}")
        except Exception as decode_error:
            await message.answer("❌ Не удалось прочитать QR-код. Убедитесь что:")
            await message.answer("- Фото хорошо освещено\n- QR-код в фокусе\n- Нет бликов")
            raise decode_error
        
        batch_id = int(qr_text)
        
        # Ищем пачку в БД
        async with db.execute(
            """SELECT batch_id, project_nm, product_nm, color, size, quantity, parts_count, seamstress_id, status
            FROM batches 
            WHERE batch_id = ? """,
            (batch_id,)
        ) as cursor:
            batch_data = await cursor.fetchone()
        
        if not batch_data:
            await message.answer("❌ Пачка не найдена")
            await state.clear()
            await show_controller_menu(message)
            return
        
        elif batch_data[8] == 'шьется' or batch_data[8] == 'создана' or batch_data[8] == 'переделка начата':
            await message.answer("❌ Пачка еще не пошита")
            await state.clear()
            await show_controller_menu(message)
            return
        elif batch_data[8] == 'пошита' or batch_data[8] == 'переделка завершена':

            await state.update_data(batch_data=batch_data)
            await state.set_state(ControllerStates.confirm_batch)
            
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
                "Присвоить пачке статус:"
            )
            
            await message.answer(
                response,
                reply_markup=controller_batch_decision()
            )
        else:
            await message.answer("❌ Пачка уже проверена")
            await state.clear()
            await show_controller_menu(message)
            return
        
    except Exception as e:
        logger.error("QR processing failed: %s", traceback.format_exc())
        logger.error(f"QR processing failed: {qr_text}")
        await message.answer("❌ Ошибка обработки QR-кода. Попробуйте еще раз!", reply_markup=cancel_button_controller())
        await state.set_state(ControllerStates.waiting_for_qr)
    

@router.callback_query(ControllerStates.confirm_batch)
async def handle_batch_decision(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        batch_id = data.get('batch_data')[0]
        seamstress_id = data.get('batch_data')[7]
        user_id = callback.from_user.id
        msg = "Действие отменено"
        
        if not batch_id:
            await callback.answer("❌ Ошибка: пачка не найдена")
            return

        action = callback.data.split('_')[-1]
    
        if action == "approve":
            async with db.execute(
                """UPDATE batches 
                SET status = 'готово', 
                    controller_id = ?,
                    control_dttm = CURRENT_TIMESTAMP
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            msg = "✅ Пачка успешно принята!"
            
        elif action == "reject":
            async with db.execute(
                """UPDATE batches 
                SET status = 'неисправимый брак', 
                    controller_id = ?,
                    control_dttm = CURRENT_TIMESTAMP
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            msg = "❌ Пачка помечена как брак!"
            
        elif action == "remake":
            # Обновляем статус
            async with db.execute(
                """UPDATE batches 
                SET status = 'брак на переделке', 
                    controller_id = ?,
                    control_dttm = CURRENT_TIMESTAMP
                WHERE batch_id = ?""",
                (user_id, batch_id)
            ) as cursor:
                await db.fetchall(cursor)
            
            # Отправляем уведомление швее
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
        await new_controller_menu(callback)
        
    except Exception as e:
        logger.error(f"Batch decision error: {traceback.format_exc()}")
        await callback.answer("⚠️ Произошла ошибка при обработке")
    finally:
        await callback.answer()