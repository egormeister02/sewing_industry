from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def role_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Менеджер", callback_data="role_manager")],
        [InlineKeyboardButton(text="Швея", callback_data="role_seamstress")],
        [InlineKeyboardButton(text="Раскройщик", callback_data="role_cutter")],
        [InlineKeyboardButton(text="Контроллер ОТК", callback_data="role_controller")],
    ])

def manager_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отчет по выплатам", callback_data="manager_payments")],
        [InlineKeyboardButton(text="Аналитика", callback_data="manager_analytics")],
        [InlineKeyboardButton(text="Список ремонтов", callback_data="manager_remakes")],
        [InlineKeyboardButton(text="Создать образец", callback_data="manager_create_product")],
    ])

def cancel_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])