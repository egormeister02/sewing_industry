from aiogram.fsm.state import StatesGroup, State

class ManagerStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_parts_number = State()
    waiting_for_product_cost = State()
    waiting_for_detail_payment = State()

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

class RemakeRequest(StatesGroup):
    waiting_for_equipment = State()
    waiting_for_description = State()
        