from aiogram import Router, types
from aiogram.filters import Command
from app.keyboards.inline import role_keyboard, cancel_button_trunk, approval_keyboard, manager_menu, seamstress_menu, cutter_menu, controller_menu, back_cancel_keyboard
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.states import RegistrationStates, RemakeRequest
from app.bot import bot
from app import db
import logging
from datetime import datetime
logger = logging.getLogger(__name__)
router = Router()

async def delete_message_reply_markup(message: types.Message):
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id - 1,
            reply_markup=None
        )
    except Exception as e:
        logger.debug(f"Could not delete message reply markup: {str(e)}")
        # Silently ignore the error as it's not critical
'''
@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Выбери свою должность:",
        reply_markup=role_keyboard()
    )

'''

    
@router.message(Command('start'))
async def cmd_start(message: types.Message):
    async with db.execute(
        "SELECT job, status FROM employees WHERE tg_id = ?", 
        (message.from_user.id,)
    ) as cursor:
        user = await cursor.fetchone()
    
    if user:
        job, status = user
        if status != 'одобрено':
            await message.answer("⏳ Ваша регистрация еще не подтверждена менеджером.")
            return
        menu_function = await get_menu_function(job)
        await message.answer("Добро пожаловать!", reply_markup=menu_function())
    else:
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
    await callback.message.edit_text("Введите ваше полное имя:")
    await callback.answer()

@router.message(RegistrationStates.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    try:
        data = await state.get_data()
        user_id = message.from_user.id

        async with db.execute(
            """INSERT INTO employees (name, job, tg_id, status)
            VALUES (?, ?, ?, 'ожидает подтверждения')""",   # на время разработки статус approved
            (data['name'], data['job'], user_id)
        ) as cursor:
            await db.fetchall(cursor)

        # Отправка уведомления менеджеру
        from app.credentials import MANAGERS_ID
        if MANAGERS_ID:
            for manager_id in MANAGERS_ID:
                    await bot.send_message(
                    chat_id=manager_id,
                    text=f"⚠️ Новая регистрация:\n\n"
                    f"ID: {user_id}\n"
                    f"Имя: {data['name']}\n"
                    f"Должность: {data['job']}\n\n"
                    f"Подтвердить регистрацию?",
                    reply_markup=approval_keyboard(user_id)
                )
        await message.answer("✅ Заявка отправлена менеджеру. Ожидайте подтверждения.",
                              reply_markup=None)      # на время разработки показывается меню должности
        await state.clear()

    except Exception as e:
        await message.answer(f"Ошибка регистрации: {str(e)}")
        await state.clear()

# Добавляем обработчики подтверждения
@router.callback_query(lambda c: c.data.startswith('approve_user_'))
async def approve_user(callback: types.CallbackQuery):
    try:
        await callback.answer()
        user_id = int(callback.data.split('_')[-1])
        
        # Обновляем статус пользователя
        async with db.execute(
            "UPDATE employees SET status = 'одобрено' WHERE tg_id = ?",
            (user_id,)
        ) as cursor:
            await db.fetchall(cursor)
        
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"✅ Пользователь {user_id} подтвержден",
            reply_markup=manager_menu()
        )

        # Активируем меню для пользователя
        async with db.execute(
            "SELECT job FROM employees WHERE tg_id = ?",
            (user_id,)
        ) as cursor:
            job = (await cursor.fetchone())[0]
            menu_func = await get_menu_function(job)
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Регистрация подтверждена!",
                reply_markup=menu_func()
            )

    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
    finally:
        await callback.answer()

@router.callback_query(lambda c: c.data.startswith('reject_user_'))
async def reject_user(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split('_')[-1])
        
        # Удаляем пользователя
        async with db.execute(
            "DELETE FROM employees WHERE tg_id = ?",
            (user_id,)
        ) as cursor:
            await db.fetchall(cursor)

        # Обновляем сообщение у менеджера
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"❌ Пользователь {user_id} отклонен",
            reply_markup=manager_menu()
        )

        # Уведомляем пользователя
        await bot.send_message(
            chat_id=user_id,
            text="❌ Ваша регистрация отклонена. Обратитесь к менеджеру."
        )

    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}")
    finally:
        await callback.answer()

async def get_menu_function(job: str):
    menu_keyboards = {
        'менеджер': manager_menu,
        'швея': seamstress_menu,
        'раскройщик': cutter_menu,
        'контролер ОТК': controller_menu
    }
    return menu_keyboards.get(job)

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

        # Получаем объект клавиатуры, а не функцию
        menu_func = await get_menu_function(job_data[0])
        menu_keyboard = menu_func()
        await state.update_data(menu_keyboard=menu_keyboard)
        
        await callback.message.answer(
            "Введите название оборудования, требующего ремонта:",
            reply_markup=cancel_button_trunk()
        )
        await state.set_state(RemakeRequest.waiting_for_equipment)
        
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
        if job_data:
            menu_func = await get_menu_function(job_data[0])
            menu_keyboard = menu_func()
            await callback.message.answer("Меню:", reply_markup=menu_keyboard)

# Обработчик кнопки "Назад" для заявки на ремонт
@router.callback_query(lambda c: c.data == 'back_step')
async def back_to_equipment(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == RemakeRequest.waiting_for_description:
        # Возврат к вводу названия оборудования
        await state.set_state(RemakeRequest.waiting_for_equipment)
        await callback.message.edit_text(
            "Введите название оборудования, требующего ремонта:",
            reply_markup=cancel_button_trunk()
        )
    elif current_state and 'waiting_for' in str(current_state):
        # Для других состояний RemakeRequest, просто отменяем операцию
        await state.clear()
        await callback.message.edit_text("Действие отменено")
        
        if 'menu_keyboard' in data:
            await callback.message.answer(
                "Возврат в меню:",
                reply_markup=data['menu_keyboard']
            )
    else:
        # Для других состояний, просто игнорируем
        pass
    
    await callback.answer()

@router.message(RemakeRequest.waiting_for_equipment)
async def process_remake_equipment(message: types.Message, state: FSMContext):
    await state.update_data(equipment=message.text)
    await delete_message_reply_markup(message)
    await message.answer(
        "Опишите проблему с оборудованием:",
        reply_markup=back_cancel_keyboard("back_step", "cancel_trunk")
    )
    await state.set_state(RemakeRequest.waiting_for_description)

@router.message(RemakeRequest.waiting_for_description)
async def process_remake_description(message: types.Message, state: FSMContext):        
    data = await state.get_data()
    try:
        # Экранируем HTML-теги в описании
        safe_description = message.text.replace('<', '&lt;').replace('>', '&gt;')
        await delete_message_reply_markup(message)
        
        async with db.execute(
            """INSERT INTO remakes 
            (equipment_nm, description, applicant_id, status, created_at)
            VALUES (?, ?, ?, 'создана', ?)""",
            (data['equipment'], safe_description, message.from_user.id, datetime.now())
        ) as cursor:
            await db.fetchall(cursor)
            
        await message.answer(
            "✅ Заявка на ремонт создана!", 
            reply_markup=data['menu_keyboard'],
            parse_mode='HTML'  # Явно указываем режим парсинга
        )
        await state.clear()
        
    except Exception as e:
        error_msg = f"Ошибка: {str(e)}".replace('<', '&lt;').replace('>', '&gt;')
        await message.answer(
            error_msg,
            parse_mode='HTML',
            reply_markup=data.get('menu_keyboard')
        )
        await state.clear()

@router.callback_query(lambda c: c.data == 'cancel_trunk')
async def cancel_trunk_actions(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Действие отменено")
    
    if 'menu_keyboard' in data:
        # Используем сохраненный объект клавиатуры
        await callback.message.answer(
            "Возврат в меню:",
            reply_markup=data['menu_keyboard']
        )
        
    await callback.answer()

async def send_payment_notification(tg_id: int, type: str, amount: int, role: str):

    try:
        payment_type = type.replace('<', '&lt;').replace('>', '&gt;')
        if payment_type == 'зарплата':
            emoji = '🧳'
            text = f"{emoji} Вам начислена {payment_type}!\nСумма: {amount} руб."
        elif payment_type == 'премия':
            emoji = '🎉'
            text = f"{emoji} Вам начислена {payment_type}!\nСумма: {amount} руб."
        elif payment_type == 'штраф':
            emoji = '⚠️'
            text = f"{emoji} Вам выписан {payment_type}!\nСумма: -{amount} руб."
        else:
            emoji = '💰'
            text = f"{emoji} Вам начислена {payment_type}!\nСумма: {amount} руб."
        
        await bot.send_message(
            chat_id=tg_id,
            text=text,
            parse_mode='HTML'
        )
        if role:
            menu_func = await get_menu_function(role)
            await bot.send_message(
                chat_id=tg_id,
            text="меню:",
            reply_markup=menu_func()
        )
        return True
        
    except Exception as e:
        logger.error(f"Payment notification error: {str(e)}")
        return False