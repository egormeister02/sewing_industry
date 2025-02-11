from aiogram.fsm.state import StatesGroup, State

class CutterStates(StatesGroup):
    waiting_for_project_name = State()
    waiting_for_product_name = State()
    waiting_for_color = State()
    waiting_for_size = State()
    waiting_for_quantity = State()
    waiting_for_parts_count = State()