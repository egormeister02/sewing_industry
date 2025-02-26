import ssl
import asyncio
import logging
logger = logging.getLogger(__name__)
from app.database import db
from app.services.dictionary import TABLE_TRANSLATIONS, COLUMN_TRANSLATIONS
from app.credentials import MANAGERS_ID
from app.bot import bot
from app.keyboards.inline import change_google_sheet
# Конфигурация повторных попыток
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды

def retry(attempts: int, delay: float, exceptions: tuple):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == attempts:
                        logger.error(f"Ошибка после {attempts} попыток: {str(e)}")
                        raise
                    logger.warning(f"Попытка {attempt} из {attempts} не удалась: {str(e)}. Повторная попытка через {delay} сек...")
                    await asyncio.sleep(delay * (2 ** (attempt - 1)))  # Экспоненциальная задержка
            return None
        return wrapper
    return decorator

# Расширенный список исключений для сетевых проблем
NETWORK_EXCEPTIONS = (
    ssl.SSLError,             # Все ошибки SSL
    TimeoutError,             # Таймауты
    ConnectionError,          # Ошибки соединения
    ConnectionResetError,     # Сброс соединения
    ConnectionRefusedError,   # Отказ в соединении
    ConnectionAbortedError,   # Прерывание соединения
    BrokenPipeError,          # Разорванное соединение
    OSError,                  # Общие ошибки ОС, включая сетевые
)

@retry(attempts=MAX_RETRIES, delay=RETRY_DELAY, exceptions=NETWORK_EXCEPTIONS)
async def safe_db_operation(func, *args, **kwargs):
    """Безопасное выполнение операций с БД с повторными попытками"""
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except NETWORK_EXCEPTIONS as e:
        logger.warning(f"Сетевая ошибка: {str(e)}. Повторная попытка...")
        raise

async def handle_google_sheets_update(request_data: dict):
    """Обработка запроса на обновление данных из Google Sheets"""
    # ... existing code ...

    sheet_name = request_data["sheet_name"]
    num_rows = request_data["num_rows"]
    row_id = request_data["row_id"]
    
    try:
        # Находим английское название таблицы по русскому имени листа
        table_name = next(k for k, v in TABLE_TRANSLATIONS.items() if v == sheet_name)
        columns = list(COLUMN_TRANSLATIONS[table_name].keys())  # Берем английские имена колонок
        id_column = columns[0]  # Первый ключ как имя колонки ID
        
        if num_rows == 1:
            try:
                if row_id == '':
                    logger.info("Попытка удаления строки")
                    error_msg = f"Если была попытка удаления строки в таблице {sheet_name}\n\
                                необходимо синхронизовать данные"
                    await _handle_mass_edit_attempt(
                        table_name=table_name,
                        error_msg=error_msg
                    )
                    return
                row_data = dict(zip(columns, request_data["entire_row"]))
                # Формируем SQL-запрос, исключаем id_column из обновляемых полей
                set_clause = ", ".join([f"{col} = ?" for col in columns if col != id_column])
                # Заменяем пустые строки на None для NULL значений в БД
                values = [row_data[col] if row_data[col] != '' else None for col in columns if col != id_column]
                values.append(row_id)  # Для WHERE условия
                logger.info(f"set_clause: {set_clause}")
                logger.info(f"values: {values}")
                
                async with db.execute(
                    f"UPDATE {table_name} SET {set_clause} WHERE {id_column} = ?",
                    tuple(values)
                ) as cursor:
                    updated_rows = cursor.rowcount
                
                if updated_rows == 0:
                    logger.warning(f"Запись {row_id} не найдена в таблице {table_name} \n создаем новую запись")
                    # Формируем полный набор значений включая ID
                    insert_values = [row_id] + values[:-1]  # Добавляем ID и убираем последний элемент (бывший WHERE param)
                    
                    async with db.execute(
                        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))})",
                        tuple(insert_values)
                    ) as cursor: 
                        await cursor.fetchall()
                    
                    logger.info(f"Успешно создана новая запись {row_id} в таблице {table_name}")
                else:
                    logger.info(f"Успешно обновлена запись {row_id} в таблице {table_name}")

            except Exception as e:
                error_msg = f"Ошибка обновления: {str(e)}"
                logger.error(error_msg)
                await _handle_update_failure(
                    table_name=table_name,
                    record_id=str(row_id),
                    sheet_name=sheet_name,
                    columns=columns,
                    error_msg=error_msg
                )
        else:
            logger.info("Попытка редактирования нескольких строк одновременно")
            error_msg = "Редактирование нескольких строк одновременно\n\
                        необходимо синхронизовать данные"
            await _handle_mass_edit_attempt(
                table_name=table_name,
                error_msg=error_msg
            )

    except StopIteration:
        error_msg = f"Не найдено соответствие для листа: {sheet_name}"
        logger.error(error_msg)
        await _handle_update_failure(
            table_name=sheet_name,
            record_id=str(row_id),
            sheet_name=sheet_name,
            columns=[],
            error_msg=error_msg
        )
    # ... existing code ...

async def _handle_mass_edit_attempt(table_name: str, error_msg: str):
    """Обработка попытки массового редактирования"""
    logger.info(f"Отправляем сообщение менеджеру {MANAGERS_ID}")
    if MANAGERS_ID:
        for manager_id in MANAGERS_ID:
            try:
                await bot.send_message(chat_id=manager_id, text=error_msg, reply_markup=change_google_sheet(table_name))
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение менеджеру {manager_id}: {str(e)}")

async def _handle_update_failure(table_name: str, record_id: str, sheet_name: str, columns: list, error_msg: str = None):
    """Обработка неудачного обновления"""

    if MANAGERS_ID:
        message = (f"⚠️ Ошибка синхронизации с Google Sheets\n\n"
                  f"• Таблица: {table_name}\n"
                  f"• ID записи: {record_id}\n"
                  f"• Лист: {sheet_name}\n"
                  f"• Ошибка: {error_msg or 'Неизвестная ошибка'}")
        
        for manager_id in MANAGERS_ID:
            try:
                await bot.send_message(chat_id=manager_id, text=message)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение менеджеру {manager_id}: {str(e)}")

    # 2. Синхронизируем данные из БД в Google Sheets
    try:
        logger.info(f"Откат изменений для таблицы {table_name}")
        async with db.execute(
            f"SELECT * FROM {table_name} WHERE {columns[0]} = ?", 
            (record_id,)
        ) as cursor:
            db_row = await cursor.fetchone()

        if db_row:
            columns = [desc[0] for desc in cursor.description]
            row_data = dict(zip(columns, db_row))
            
            # Синхронизация с повторными попытками
            await safe_db_operation(
                db.sheets.sync_single_row,
                table_name=table_name,
                row_data=row_data,
                action_type='UPDATE'
            )
        else:
            logger.warning(f"Запись {record_id} не найдена в БД, удаляем из таблицы")
            await safe_db_operation(
                db.sheets.delete_row,
                sheet_name,
                {'id': record_id}
            )

    except Exception as sync_error:
        logger.error(f"Ошибка при синхронизации после неудачного обновления: {str(sync_error)}")

async def sync_db_to_sheets(table_name: str):
    """Полная синхронизация таблицы БД с Google Sheets"""
    try:
        # 1. Получаем русское название листа
        sheet_name = TABLE_TRANSLATIONS.get(table_name)
        if not sheet_name:
            raise ValueError(f"Нет конфигурации для таблицы {table_name}")

        # 2. Загружаем данные из Google Sheets с повторными попытками
        try:
            sheet_data = await safe_db_operation(
                db.sheets.get_sheet_data,
                sheet_name=sheet_name
            )
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных из Google Sheets: {str(e)}")
            raise ValueError(f"Не удалось загрузить данные из таблицы: {str(e)}")
        
        # Преобразуем данные из списка списков в список словарей
        if len(sheet_data) > 1:  # Проверяем, есть ли данные, кроме заголовков
            headers = sheet_data[0]
            sheet_records = []
            for row in sheet_data[1:]:
                if row:  # Проверяем, что строка не пустая
                    # Заполняем пустые значения в конце строки
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    record = {headers[i]: value.strip() if isinstance(value, str) else value for i, value in enumerate(row) if i < len(headers)}
                    sheet_records.append(record)
        else:
            sheet_records = []

        # 3. Преобразуем данные
        columns = list(COLUMN_TRANSLATIONS[table_name].keys())
        id_column = columns[0]
        
        transformed_data = {}
        for row in sheet_records:
            # Получаем значение ID-колонки из заголовка в Google Sheets
            sheet_id_column = COLUMN_TRANSLATIONS[table_name][id_column]
            record_id = row.get(sheet_id_column, '')
            if record_id:  # Игнорируем строки без ID
                # Заполняем словарь, преобразуя имена полей из русских в английские
                record_data = {}
                for col in columns:
                    sheet_column = COLUMN_TRANSLATIONS[table_name][col]
                    value = row.get(sheet_column, '')
                    # Преобразуем пустые строки в None
                    record_data[col] = value if value != '' else None
                transformed_data[str(record_id)] = record_data

        # 4. Получаем текущие данные из БД с повторными попытками
        try:
            async with db.execute(f"SELECT * FROM {table_name}") as cursor:
                db_rows = await cursor.fetchall()
                db_columns = [desc[0] for desc in cursor.description]
        except Exception as e:
            logger.error(f"Ошибка при чтении данных из БД: {str(e)}")
            raise ValueError(f"Не удалось прочитать данные из базы данных: {str(e)}")
        
        db_data = {
            str(row[0]): dict(zip(db_columns, row)) 
            for row in db_rows
        }

        # 5. Вычисляем различия
        to_insert = []
        to_update = []
        
        for record_id, row in transformed_data.items():
            if record_id not in db_data:
                to_insert.append(row)
            elif row != db_data[record_id]:
                to_update.append(row)

        to_delete = [id_ for id_ in db_data if id_ not in transformed_data]

        # 6. Выполняем синхронизацию последовательно с обработкой ошибок
        success_inserts = 0
        success_updates = 0
        success_deletes = 0
        
        # Вставка новых записей
        for item in to_insert:
            try:
                placeholders = ', '.join(['?'] * len(columns))
                async with db.execute(
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                    [item.get(col) for col in columns]  # None будет автоматически подставлен для пустых значений
                ) as cursor:
                    await cursor.fetchall()
                success_inserts += 1
            except Exception as e:
                logger.error(f"Ошибка при вставке записи {item.get(id_column)}: {str(e)}")

        # Обновление существующих
        for item in to_update:
            try:
                set_clause = ", ".join([f"{col} = ?" for col in columns[1:]])
                values = [item.get(col) for col in columns[1:]]  # None для пустых значений
                values.append(item.get(id_column))
                async with db.execute(
                    f"UPDATE {table_name} SET {set_clause} WHERE {id_column} = ?",
                    values
                ) as cursor:
                    await cursor.fetchall()
                success_updates += 1
            except Exception as e:
                logger.error(f"Ошибка при обновлении записи {item.get(id_column)}: {str(e)}")

        # Удаление отсутствующих
        for id_ in to_delete:
            try:
                async with db.execute(
                    f"DELETE FROM {table_name} WHERE {id_column} = ?",
                    [id_]
                ) as cursor:
                    await cursor.fetchall()
                success_deletes += 1
            except Exception as e:
                logger.error(f"Ошибка при удалении записи {id_}: {str(e)}")

        logger.info(f"Синхронизация {table_name} завершена. "
                  f"Добавлено: {success_inserts}/{len(to_insert)}, "
                  f"Обновлено: {success_updates}/{len(to_update)}, "
                  f"Удалено: {success_deletes}/{len(to_delete)}")

    except Exception as e:
        logger.error(f"Ошибка синхронизации {table_name}: {str(e)}")
        raise