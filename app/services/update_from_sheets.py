import ssl
import asyncio
import logging
logger = logging.getLogger(__name__)
from app.database import db
from app.services.dictionary import TABLE_TRANSLATIONS, COLUMN_TRANSLATIONS
from app.credentials import MANAGERS_ID
from app.bot import bot

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
                        raise
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

@retry(attempts=MAX_RETRIES, delay=RETRY_DELAY, 
       exceptions=(ssl.SSLError, TimeoutError, ConnectionError))
async def safe_db_operation(func, *args, **kwargs):
    """Безопасное выполнение операций с БД с повторными попытками"""
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return await func(*args, **kwargs)
    except (ssl.SSLError, TimeoutError, ConnectionError) as e:
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
                    error_msg = "Попытка удаления строки"
                    cell_ref = f"Строка {row_id}"
                    await _handle_mass_edit_attempt(
                        sheet_name=sheet_name,
                        cell_reference=cell_ref,
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
            error_msg = "Попытка редактирования нескольких строк одновременно"
            cell_ref = f"Строка {row_id}"
            await _handle_mass_edit_attempt(
                sheet_name=sheet_name,
                cell_reference=cell_ref,
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

async def _handle_mass_edit_attempt(sheet_name: str, cell_reference: str, error_msg: str):
    """Обработка попытки массового редактирования"""
    logger.info(f"Отправляем сообщение менеджеру {MANAGERS_ID}")
    if MANAGERS_ID:
        message = (f"⚠️ Обнаружено массовое редактирование\n\n"
                  f"• Лист: {sheet_name}\n"
                  f"• Выбранные ячейки: {cell_reference}\n"
                  f"• Ошибка: {error_msg}\n\n"
                  "Пожалуйста, редактируйте ячейки по одной!")
        
        
        for manager_id in MANAGERS_ID:
            try:
                await bot.send_message(chat_id=manager_id, text=message)
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

        # 2. Загружаем данные из Google Sheets
        sheet_data = await safe_db_operation(
            db.sheets.get_all_records,
            sheet_name=sheet_name,
            as_dict=True
        )

        # 3. Преобразуем данные
        columns = list(COLUMN_TRANSLATIONS[table_name].keys())
        id_column = columns[0]
        
        transformed_data = {
            str(row[COLUMN_TRANSLATIONS[table_name][id_column]]): {
                col: row[COLUMN_TRANSLATIONS[table_name][col]] 
                for col in columns
            }
            for row in sheet_data if row
        }

        # 4. Получаем текущие данные из БД
        async with db.execute(f"SELECT * FROM {table_name}") as cursor:
            db_rows = await cursor.fetchall()
            db_columns = [desc[0] for desc in cursor.description]
        
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

        # 6. Выполняем синхронизацию
        async with db.atomic():
            # Вставка новых записей
            if to_insert:
                await safe_db_operation(
                    db.execute_many,
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))})",
                    [tuple(item[col] for col in columns) for item in to_insert]
                )

            # Обновление существующих
            if to_update:
                set_clause = ", ".join([f"{col} = ?" for col in columns[1:]])
                params = [
                    (*[item[col] for col in columns[1:]], item[id_column]) 
                    for item in to_update
                ]
                await safe_db_operation(
                    db.execute_many,
                    f"UPDATE {table_name} SET {set_clause} WHERE {id_column} = ?",
                    params
                )

            # Удаление отсутствующих
            if to_delete:
                await safe_db_operation(
                    db.execute_many,
                    f"DELETE FROM {table_name} WHERE {id_column} = ?",
                    [(id_,) for id_ in to_delete]
                )

        logger.info(f"Синхронизация {table_name} завершена. "
                   f"Добавлено: {len(to_insert)}, "
                   f"Обновлено: {len(to_update)}, "
                   f"Удалено: {len(to_delete)}")

    except Exception as e:
        logger.error(f"Ошибка синхронизации {table_name}: {str(e)}")
        raise