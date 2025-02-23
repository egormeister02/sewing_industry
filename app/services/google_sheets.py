import logging
import asyncio
from typing import Dict, List, Optional
from google.oauth2.service_account import Credentials
import re
from datetime import datetime
import hashlib
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.credentials import GOOGLE_CREDS, SPREADSHEET_ID
from app.services.dictionary import COLUMN_TRANSLATIONS, TABLE_TRANSLATIONS

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    def __init__(self, db_instance=None):  # Добавлен параметр для инъекции зависимости
        self.creds = Credentials.from_service_account_file(
            GOOGLE_CREDS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=self.creds)
        self.sheets = self.service.spreadsheets()
        self.db = db_instance  # Сохраняем ссылку на экземпляр БД

    async def _execute_api_call(self, func, *args, **kwargs):
        """Обработка асинхронных вызовов API"""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs).execute())
        except HttpError as e:
            logger.error(f"Google API Error: {e}")
            raise

    async def create_new_spreadsheet(self, title: str) -> str:
        """Создать новую таблицу"""
        spreadsheet = {
            'properties': {
                'title': title,
                'locale': 'ru_RU'
            }
        }
        result = await self._execute_api_call(
            self.service.spreadsheets().create,
            body=spreadsheet
        )
        return result['spreadsheetId']

    async def ensure_sheet_exists(self, table_name: str) -> None:
        """Проверка и создание листа с обработкой спецсимволов"""
        # Переводим название таблицы на русский
        sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
        clean_name = self._sanitize_sheet_name(sheet_name)
        
        # Получаем список всех листов
        spreadsheet = await self._execute_api_call(
            self.sheets.get,
            spreadsheetId=SPREADSHEET_ID,
            includeGridData=False
        )
        
        # Проверяем существование листа
        existing_sheets = [s['properties']['title'] for s in spreadsheet['sheets']]
        if clean_name in existing_sheets:
            await self._execute_api_call(
                self.sheets.values().clear,
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A:O",
                body={}
            )
            return
    
        # Создаем новый лист
        await self._execute_api_call(
            self.sheets.batchUpdate,
            spreadsheetId=SPREADSHEET_ID,
            body={
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': clean_name,
                            'gridProperties': {'rowCount': 1000, 'columnCount': 20}
                        }
                    }
                }]
            }
        )
    
    def _sanitize_sheet_name(self, name: str) -> str:
        """Очистка названия листа по правилам Google"""
        # Максимальная длина 100 символов
        name = name[:100]
        # Замена запрещенных символов
        return name.translate(str.maketrans({
            ':': '_',
            '/': '_',
            '?': '',
            '*': '',
            '[': '(',
            ']': ')'
        })).strip("'")
    

    async def _get_column_constraints(self, table_name: str) -> Dict[str, List[str]]:
        """Получение ограничений с исправленным парсингом многострочных CHECK"""
        constraints = {}
        try:
            async with self.db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", 
                (table_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {}
                
                create_stmt = row[0]
                logger.debug(f"SQL schema for {table_name}: {create_stmt}")

                # Ищем все CHECK ограничения с поддержкой переносов строк
                checks = re.findall(
                    r'CHECK\s*\(\s*((?:[^()]|\([^)]*\))*)\s*\)', 
                    create_stmt, 
                    re.IGNORECASE | re.DOTALL
                )

                for check in checks:
                    # Нормализуем пробельные символы и переносы строк
                    check = re.sub(r'\s+', ' ', check).strip()
                    
                    # Ищем шаблоны вида "column IN ('val1', 'val2')" с учётом возможных пробелов
                    match = re.search(
                        r'(\b\w+\b)\s+IN\s*\(\s*((?:\s*\'[^\']+\'\s*,?)+)\s*\)', 
                        check, 
                        re.IGNORECASE
                    )
                    
                    if match:
                        col = match.group(1).lower()
                        values_str = match.group(2)
                        values = [v.strip().strip("'\"") for v in re.split(r"'\s*,\s*'", values_str)]
                        constraints[col] = values
                        logger.info(f"Found constraints for {col}: {values}")
                    else:
                        logger.warning(f"Unsupported CHECK format: {check}")

        except Exception as e:
            logger.error(f"Error parsing constraints: {str(e)}")
        
        return constraints
    
    async def _get_column_types(self, table_name: str) -> Dict[str, str]:
        """Получение типов данных колонок из схемы БД"""
        column_types = {}
        async with self.db.execute(f"PRAGMA table_info({table_name})") as cursor:
            for row in await cursor.fetchall():
                col_name = row[1].lower()
                col_type = row[2].upper()
                # Нормализация типов
                if 'INT' in col_type:
                    col_type = 'INTEGER'
                elif 'REAL' in col_type or 'FLOAT' in col_type:
                    col_type = 'REAL'
                elif 'DATE' in col_type or 'TIME' in col_type or 'DATETIME' in col_type:
                    col_type = 'DATETIME'
                else:
                    col_type = 'TEXT'
                column_types[col_name] = col_type
        return column_types

    def _get_validation_rule(self, col_type: str) -> Optional[Dict]:
        if col_type == 'INTEGER':
            return {
                "condition": {  # condition внутри rule
                    "type": "NUMBER_BETWEEN",
                    "values": [
                        {"userEnteredValue": "0"},
                        {"userEnteredValue": "20000000000"}
                    ]
                },
                "strict": True  # strict на том же уровне, что и condition
            }
        elif col_type == 'DATETIME':
            return {
                "condition": {
                    "type": "DATE_BEFORE",
                    "values": [{"userEnteredValue": "=TODAY()+365"}]
                },
                "strict": True,
                "inputMessage": "Формат: ДД.ММ.ГГГГ ЧЧ:MM"
            }
        return None

    async def _apply_data_validation(self, table_name: str, constraints: Dict[str, List[str]]):
        """Применение правил валидации к листу с учетом перевода названий таблиц"""
        # Переводим название таблицы на русский
        sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
        
        if not constraints:
            logger.info(f"No constraints to apply for {sheet_name}")
            return

        try:
            # Получаем данные и индексы колонок
            data = await self.get_sheet_data(sheet_name)
            if not data:
                logger.warning(f"No data found for sheet {sheet_name}")
                return
                
            # Создаем обратный словарь для перевода русских названий в английские
            translations = COLUMN_TRANSLATIONS.get(table_name, {})
            reverse_translations = {v.lower(): k for k, v in translations.items()}
            
            # Сопоставляем русские заголовки с английскими именами колонок
            columns = {col.lower(): idx for idx, col in enumerate(data[0])}
            logger.debug(f"Columns for {sheet_name}: {columns}")

            column_types = await self._get_column_types(table_name)
            logger.info(f"Detected column types for {table_name}: {column_types}")

            # Получаем ID листа
            sheet_id = await self._get_sheet_id(table_name)
            logger.info(f"Applying validation to sheet {sheet_name} (ID: {sheet_id})")

            requests = []

            def process_validation(db_col, validation_type, values=None):
                # Общая логика обработки колонки
                russian_col = translations.get(db_col, db_col)
                if russian_col.lower() not in columns:
                    return None
                    
                col_index = columns[russian_col.lower()]
                range_def = {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1
                }

                # Формируем правило валидации в зависимости от типа
                if validation_type == 'type':
                    # Получаем полное правило валидации из отдельного метода
                    validation_rule = self._get_validation_rule(col_type)
                    if not validation_rule:
                        return None
                        
                    rule = {
                        **validation_rule,
                        "strict": True,
                        "showCustomUi": True
                    }
                    logger.debug(f"Added type validation for {russian_col} ({values})")
                else: # constraint
                    rule = {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [{"userEnteredValue": v} for v in values]
                        },
                        "strict": True,
                        "showCustomUi": True
                    }
                    logger.debug(f"Added constraint for {russian_col} with {len(values)} values")

                return {
                    "setDataValidation": {
                        "range": range_def,
                        "rule": rule
                    }
                }

            # Обрабатываем валидации с учетом структуры _get_validation_rule
            for db_col, col_type in column_types.items():
                if request := process_validation(db_col, 'type', col_type):
                    requests.append(request)

            for db_col, values in constraints.items():
                if request := process_validation(db_col, 'constraint', values):
                    requests.append(request)
                else:
                    logger.warning(f"Column {translations.get(db_col, db_col)} not found in sheet {sheet_name}")

            if requests:
                logger.info(f"Sending {len(requests)} validation requests for {sheet_name}")
                await self._execute_api_call(
                    self.sheets.batchUpdate,
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": requests}
                )
                logger.info(f"Successfully applied validations to {sheet_name}")
            else:
                logger.warning(f"No validation requests generated for {sheet_name}")

        except HttpError as e:
            logger.error(f"Google API Error applying validation: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in validation: {str(e)}")
            raise

    async def initialize_sheet(self, table_name: str) -> None:
        """Инициализация структуры листа"""
        # Переводим название таблицы на русский
        sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
        await self.ensure_sheet_exists(sheet_name)
        # Получаем метаданные таблицы
        async with self.db.execute(f"PRAGMA table_info({table_name})") as cursor:
            columns_info = await cursor.fetchall()
            columns = [row[1] for row in columns_info]
            column_types = {row[1]: row[2].upper() for row in columns_info}
        
        # Переводим заголовки
        translated_columns = [
            COLUMN_TRANSLATIONS.get(table_name, {}).get(col, col)
            for col in columns
        ]
        
        # Записываем заголовки
        await self._execute_api_call(
            self.sheets.values().update,
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption='USER_ENTERED',
            body={'values': [translated_columns]}
        )
        
        # Применяем форматирование дат
        if any(col_type == 'DATETIME' for col_type in column_types.values()):
            sheet_id = await self._get_sheet_id(sheet_name)
            await self._execute_api_call(
                self.sheets.batchUpdate,
                spreadsheetId=SPREADSHEET_ID,
                body={
                    "requests": [{
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "numberFormat": {
                                        "type": "DATE_TIME",
                                        "pattern": "dd.MM.yyyy HH:mm"
                                    }
                                }
                            },
                            "fields": "userEnteredFormat.numberFormat"
                        }
                    } for col_idx, col_name in enumerate(columns) 
                    if column_types.get(col_name) == 'DATETIME']
                }
            )
        
        # Применяем валидацию
        constraints = await self._get_column_constraints(table_name)
        await self._apply_data_validation(table_name, constraints)

    async def sync_single_row(self, table_name: str, row_data: dict, action_type: str):
        """Синхронизация одной строки с учетом типа действия"""
        try:
            sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
            column_mapping = COLUMN_TRANSLATIONS.get(table_name, {})
            
            # Получаем английское и русское название колонки ID
            pk_column_en = next(iter(column_mapping.keys()))  # Первый ключ словаря (англ)
            pk_column_ru = column_mapping[pk_column_en]       # Соответствующее русское название
            
            if action_type == 'INSERT':
                values = [row_data.get(col) for col in column_mapping.keys()]
                await self._execute_api_call(
                    self.sheets.values().append,
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{sheet_name}!A:A",
                    valueInputOption='USER_ENTERED',
                    body={'values': [values]}
                )
                
            elif action_type == 'UPDATE':
                # Ищем строку по ID в первом столбце
                result = await self._execute_api_call(
                    self.sheets.values().get,
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{sheet_name}!A:Z"
                )
                rows = result.get('values', [])
                
                # Ищем индекс строки с совпадающим ID (первый столбец)
                row_index = next(
                    (i+1 for i, row in enumerate(rows[1:]) 
                     if row and row[0] == str(row_data[pk_column_en])),
                    None
                )
                
                if row_index:
                    # Формируем новые значения в правильном порядке колонок
                    update_values = [row_data.get(col) for col in column_mapping.keys()]
                    await self._execute_api_call(
                        self.sheets.values().update,
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"{sheet_name}!A{row_index+1}",
                        valueInputOption='USER_ENTERED',
                        body={'values': [update_values]}
                    )

        except HttpError as e:
            logger.error(f"Google Sheets API Error: {str(e)}")

    async def delete_row(self, sheet_name: str, row_data: dict):
        """Удаление строки из таблицы"""
        try:
            sheet_id = await self._get_sheet_id(sheet_name)
            await self._execute_api_call(
                self.sheets.batchUpdate,
                spreadsheetId=SPREADSHEET_ID, 
                body={
                    "requests": [{
                        "deleteDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": row_data['audit_id'],
                                "endIndex": row_data['audit_id'] + 1
                            }
                        }
                    }]
                }
            )
        except HttpError as e:
            logger.error(f"Google Sheets Delete Error: {str(e)}")

    def _convert_row_values(self, row_data: dict) -> list:
        """Конвертация данных строки для Google Sheets"""
        return [
            row_data.get(col, '') 
            for col in COLUMN_TRANSLATIONS.get(row_data['table_name'], {}).keys()
        ]
    # Обновленная функция для синхронизации данных
    async def sync_data_to_sheet(self, table_name: str) -> None:
        """Синхронизация данных с предварительной очисткой листа"""
        # Переводим название таблицы на русский
        sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
        
        
        # Получаем типы колонок и маппинг
        column_types = await self._get_column_types(table_name)
        column_mapping = COLUMN_TRANSLATIONS.get(table_name, {})
        
        # Получаем данные
        async with self.db.execute(f"SELECT * FROM {table_name}") as cursor:
            data = await cursor.fetchall()

        # Преобразуем данные
        values = []
        for row in data:
            converted_row = []
            for idx, (col_name, value) in enumerate(zip(column_mapping.keys(), row)):
                if column_types.get(col_name) == 'DATETIME':
                    if isinstance(value, datetime):
                        converted_value = value.strftime("%d.%m.%Y %H:%M")
                    elif isinstance(value, str):
                        converted_value = datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
                    else:
                        converted_value = ""
                else:
                    converted_value = value
                converted_row.append(converted_value)
            values.append(converted_row)

        # Записываем новые данные
        await self._execute_api_call(
            self.sheets.values().update,
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A2",
            valueInputOption='USER_ENTERED',
            body={'values': values}
        )

    async def full_sync(self) -> Dict[str, str]:
        """Полная синхронизация всех таблиц"""
        results = {}
        async with self.db.execute("""SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        AND name NOT LIKE 'sqlite_%' 
                        AND name NOT LIKE '%_audit'""") as cursor:
            tables = [row[0] for row in await cursor.fetchall()]

        for table in tables:
            try:
                await self.sync_data_to_sheet(table)
                results[table] = 'OK'
            except Exception as e:
                results[table] = f"Error: {str(e)}"
                logger.error(f"Sync failed for {table}: {e}")
        return results

    async def _get_sheet_id(self, table_name: str) -> int:
        """Получение ID листа по названию"""
        # Переводим название таблицы на русский
        sheet_name = TABLE_TRANSLATIONS.get(table_name, table_name)
        
        spreadsheet = await self._execute_api_call(
            self.sheets.get,
            spreadsheetId=SPREADSHEET_ID,
            includeGridData=False
        )
        for sheet in spreadsheet['sheets']:
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        raise ValueError(f"Sheet {sheet_name} not found")

    async def get_sheet_data(self, sheet_name: str) -> List[List[str]]:
        """Получить данные из листа"""
        result = await self._execute_api_call(
            self.sheets.values().get,
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A:Z"
        )
        return result.get('values', [])

    async def configure_auto_sync(self, interval: int = 3600) -> None:
        """Настройка периодической синхронизации"""
        async def sync_task():
            while True:
                await self.full_sync()
                await asyncio.sleep(interval)

        asyncio.create_task(sync_task())
    
    def _reverse_translate(self, table_name: str, ru_name: str) -> str:
        """Обратный перевод названия колонки"""
        translations = COLUMN_TRANSLATIONS.get(table_name, {})
        reverse_dict = {v: k for k, v in translations.items()}
        return reverse_dict.get(ru_name, ru_name)