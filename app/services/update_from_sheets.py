import asyncio
import logging
logger = logging.getLogger(__name__)
from app.database import db
from app.services.dictionary import TABLE_TRANSLATIONS, COLUMN_TRANSLATIONS
from app.credentials import MANAGERS_ID
from app.bot import bot

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
                    await cursor.fetchall()
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
        # Получаем актуальные данные из БД
        async with db.execute(
            f"SELECT * FROM {table_name} WHERE {columns[0]} = ?", 
            (record_id,)
        ) as cursor:
            db_row = await cursor.fetchone()
        db_row = await cursor.fetchone()

        if db_row:
            # Преобразуем в словарь с именами колонок
            columns = [desc[0] for desc in cursor.description]
            row_data = dict(zip(columns, db_row))
            
            # Синхронизируем с Google Sheets
            await db.sheets.sync_single_row(
                table_name=table_name,
                row_data=row_data,
                action_type='UPDATE'
            )
        else:
            logger.warning(f"Запись {record_id} не найдена в БД, удаляем из таблицы")
            await db.sheets.delete_row(sheet_name, {'id': record_id})

    except Exception as sync_error:
        logger.error(f"Ошибка при синхронизации после неудачного обновления: {str(sync_error)}")