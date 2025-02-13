from .models import Database, init_db

# Инициализация базы данных
db = Database()

# Экспорт функций и объектов
__all__ = ["db", "init_db"]