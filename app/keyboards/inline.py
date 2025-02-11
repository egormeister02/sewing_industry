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

def seamstress_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="seamstress_data")],
        [InlineKeyboardButton(text="Мои выплаты", callback_data="seamstress_payments")],
        [InlineKeyboardButton(text="Взять пачку", callback_data="seamstress_make_batch")],
        [InlineKeyboardButton(text="Заявка на ремонт", callback_data="seamstress_repair")],
    ])

def cutter_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="cutter_data")],
        [InlineKeyboardButton(text="Мои выплаты", callback_data="cutter_payments")],
        [InlineKeyboardButton(text="Создать пачку", callback_data="cutter_create_batch")],
        [InlineKeyboardButton(text="Заявка на ремонт", callback_data="cutter_repair")],
    ])

def controller_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="controller_data")],
        [InlineKeyboardButton(text="Мои выплаты", callback_data="controller_payments")],
        [InlineKeyboardButton(text="Проверка качества", callback_data="controller_quality_check")],
        [InlineKeyboardButton(text="Статистика брака", callback_data="controller_defect_stats")],
    ])

