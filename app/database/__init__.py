from .models import Database, init_db
from .crud import create_product

# Инициализация базы данных
db = Database()

# Экспорт функций и объектов
__all__ = ["db", "create_product", "init_db"]