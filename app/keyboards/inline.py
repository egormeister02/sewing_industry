from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.dictionary import TABLE_TRANSLATIONS

def role_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Швея", callback_data="role_швея")],
        [InlineKeyboardButton(text="Раскройщик", callback_data="role_раскройщик")],
        [InlineKeyboardButton(text="Контроллер ОТК", callback_data="role_контролер ОТК")],
    ])

def manager_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Данные", callback_data="manager_data")],
        [InlineKeyboardButton(text="Аналитика", callback_data="manager_analytics")],
        [InlineKeyboardButton(text="Список ремонтов", callback_data="manager_remakes")],
        [InlineKeyboardButton(text="Создать образец", callback_data="manager_create_product")],
        [InlineKeyboardButton(text="Создать пачку", callback_data="manager_create_batch")],
        [InlineKeyboardButton(text="Проверка пачки", callback_data="manager_check_batch")],
    ])

def approval_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_user_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_user_{user_id}")
        ]
    ])

def seamstress_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="seamstress_data"),
         InlineKeyboardButton(text="Мои выплаты", callback_data="seamstress_payments")],
        [InlineKeyboardButton(text="Взять пачку", callback_data="seamstress_take_batch"),
         InlineKeyboardButton(text="Мои пачки", callback_data="seamstress_batches")],
        [InlineKeyboardButton(text="Заявка на ремонт", callback_data="repair")]
    ])

def seamstress_batch():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data="accept_batch"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data="decline_batch")
        ]
    ])

def seamstress_batches_menu(batches):
    buttons = [
        [InlineKeyboardButton(text=f"Пачка #{batch[0]}", callback_data=f"seamstress_batch_{batch[0]}")]
        for batch in batches
    ]
    buttons.append([InlineKeyboardButton(text="OK", callback_data="seamstress_ok")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def seamstress_finish_batch():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить", callback_data="seamstress_finish_batch"),
         InlineKeyboardButton(text="Отмена", callback_data="seamstress_cancel_finish_batch")]
    ])

def cutter_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="cutter_data")],
        [InlineKeyboardButton(text="Мои выплаты", callback_data="cutter_payments")],
        [InlineKeyboardButton(text="Создать пачку", callback_data="cutter_create_batch")],
        [InlineKeyboardButton(text="Заявка на ремонт", callback_data="repair")],
    ])

def controller_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="controller_data")],
        [InlineKeyboardButton(text="Мои выплаты", callback_data="controller_payments")],
        [InlineKeyboardButton(text="Проверка пачки", callback_data="controller_take_batch")],
        [InlineKeyboardButton(text="Заявка на ремонт", callback_data="repair")],
    ])

def controller_batch_decision():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="batch_approve"),
            InlineKeyboardButton(text="❌ Брак", callback_data="batch_reject")
        ],
        [
            InlineKeyboardButton(text="🔄 На переделку", callback_data="batch_remake"),
            InlineKeyboardButton(text="⏪ Отмена", callback_data="cancel_control")
        ]
    ])

def cancel_button_manager():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_manager")]
    ])

def cancel_button_seamstress():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_seamstress")]
    ])

def cancel_button_cutter():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_cutter")]
    ])

def cancel_button_controller():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_controller")]
    ])

def cancel_button_trunk():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_trunk")]
    ])

def change_google_sheet(table_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Внести изменения", callback_data=f"change_google_sheet_{table_name}")],
        [InlineKeyboardButton(text="↩️ Откатить", callback_data=f"rollback_google_sheet_{table_name}")],
        [InlineKeyboardButton(text="Игнорировать", callback_data="ignore_google_sheet")]
    ])

def tables_selector():
    """Клавиатура для выбора таблицы данных"""
    buttons = []
    
    for table_name, table_title in TABLE_TRANSLATIONS.items():
        buttons.append([InlineKeyboardButton(text=table_title, callback_data=f"select_table_{table_name}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_manager_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def table_actions(table_name: str):
    """Клавиатура для выбора действия с таблицей"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Google Sheet → БД", callback_data=f"sync_db_to_sheets_{table_name}")],
        [InlineKeyboardButton(text="📋 БД → Google Sheet", callback_data=f"sync_data_to_sheet_{table_name}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tables_selection")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_manager_menu")]
    ])

def back_cancel_keyboard(back_callback: str = "back_step", cancel_callback: str = "cancel_cutter"):
    """Клавиатура с кнопками Назад и Отмена"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)
        ]
    ])