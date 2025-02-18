from .models import Database, init_db

# Инициализация будет выполнена позже
db = Database()

__all__ = ["db", "init_db"]