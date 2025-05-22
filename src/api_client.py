import requests
import json
from typing import Dict, Any, Optional
from config.config import IIKO_API_BASE_URL, IIKO_API_LOGIN, IIKO_API_PASSWORD

class IikoApiClient:
    def __init__(self):
        self.base_url = IIKO_API_BASE_URL
        self.token = None
        
    def authenticate(self) -> str:
        """Получение токена авторизации"""
        auth_url = f"{self.base_url}/auth"
        params = {
            'login': IIKO_API_LOGIN,
            'pass': IIKO_API_PASSWORD
        }
        
        response = requests.get(auth_url, params=params)
        response.raise_for_status()
        
        self.token = response.text.strip().strip('"')
        return self.token
    
    def get_products(self, include_deleted: bool = False) -> list:
        """Получение списка продуктов (пагинация в IIKO API не работает корректно)"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        products_url = f"{self.base_url}/v2/entities/products/list"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'includeDeleted': str(include_deleted).lower()
        }
        
        logger.info("Загрузка всех продуктов из API...")
        
        response = requests.get(products_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        products_data = response.json()
        
        # Проверяем уникальность ID
        product_ids = [p.get('id') for p in products_data if p.get('id')]
        unique_ids = set(product_ids)
        
        if len(product_ids) != len(unique_ids):
            duplicates_count = len(product_ids) - len(unique_ids)
            logger.warning(f"Обнаружены дубликаты ID: {duplicates_count} дубликатов из {len(product_ids)} товаров")
        
        logger.info(f"Загружено {len(products_data)} продуктов, уникальных ID: {len(unique_ids)}")
        
        return products_data
    
    def get_stores(self) -> list:
        """Получение списка складов"""
        import logging
        import xml.etree.ElementTree as ET
        from io import StringIO
        
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        stores_url = f"{self.base_url}/corporation/stores"
        params = {
            'key': self.token,
            'revisionFrom': -1
        }
        
        logger.info(f"Загрузка списка складов...")
        
        response = requests.get(stores_url, params=params)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        # Парсинг XML-ответа
        try:
            xml_data = response.text
            root = ET.fromstring(xml_data)
            
            stores_data = []
            for store_elem in root.findall('./corporateItemDto'):
                store_data = {
                    'id': store_elem.findtext('id'),
                    'parentId': store_elem.findtext('parentId'),
                    'code': store_elem.findtext('code'),
                    'name': store_elem.findtext('name'),
                    'type': store_elem.findtext('type')
                }
                stores_data.append(store_data)
                
            logger.info(f"Загружено {len(stores_data)} складов")
            return stores_data
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге XML-ответа: {e}")
            logger.debug(f"Полученный XML: {response.text[:1000]}...")
            raise
    
    def analyze_products_structure(self) -> Dict[str, set]:
        """Анализ структуры данных продуктов"""
        products_data = self.get_products()
        
        # Собираем все уникальные ключи
        all_keys = set()
        nested_structures = {}
        
        for product in products_data:
            all_keys.update(product.keys())
            
            # Анализируем вложенные структуры
            for key, value in product.items():
                if isinstance(value, dict):
                    nested_structures[key] = set(value.keys())
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    nested_structures[f"{key}[]"] = set(value[0].keys())
        
        return {
            'main_keys': all_keys,
            'nested_structures': nested_structures
        }
    
    def get_sales(self, start_date=None, end_date=None) -> list:
        """Получение данных о продажах
        
        :param start_date: Начальная дата в формате YYYY-MM-DD
        :param end_date: Конечная дата в формате YYYY-MM-DD
        :return: Список продаж
        """
        import logging
        from datetime import datetime, timedelta
        
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
        
        # Если даты не указаны, берем последние 7 дней
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        sales_url = f"{self.base_url}/v2/reports/olap"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        params = {
            'key': self.token
        }
        
        # Формируем тело запроса в соответствии с OLAP API
        request_body = {
            "reportType": "SALES",
            "groupByRowFields": [
                "OrderNum",
                "Department", 
                "DishName",
                "DishCode",
                "DishMeasureUnit",
                "PrechequeTime",
                "DeletedWithWriteoff",
                "CashRegisterName",
                "CashRegisterName.Number",
                "CashRegisterName.CashRegisterSerialNumber",
                "FiscalChequeNumber",
                "OrderType",
                "Store.Name",
                "Department.Id",
                "CloseTime",
                "PayTypes",
                "OrderIncrease.Type",
                "Storned"  # Добавляем флаг отмены чека
            ],
            "aggregateFields": [
                "DishAmountInt",
                "DishSumInt",
                "DishDiscountSumInt",
                "DishReturnSum",
                "OrderItems",
                "IncreaseSum"
            ],
            "filters": {
                "OpenDate.Typed": {
                    "filterType": "DateRange",
                    "periodType": "CUSTOM",
                    "from": start_date,
                    "to": end_date
                },
                "OrderDeleted": {
                    "filterType": "IncludeValues",
                    "values": ["NOT_DELETED"]
                },
                "DeletedWithWriteoff": {
                    "filterType": "IncludeValues",
                    "values": [
                        "NOT_DELETED"  # Оставляем только неудаленные продажи
                    ]
                },
                "Storned": {
                    "filterType": "IncludeValues",
                    "values": ["FALSE"]  # Исключаем отмененные чеки
                }
            }
        }
        
        logger.info(f"Загрузка продаж с {start_date} по {end_date}...")
        
        response = requests.post(sales_url, params=params, headers=headers, json=request_body)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        sales_data = response.json()
        
        if isinstance(sales_data, dict) and 'data' in sales_data:
            sales_data = sales_data['data']
            
        # Преобразуем данные из OLAP в формат, который ожидает синхронизатор
        formatted_sales = []
        skipped_storned = 0
        skipped_returns = 0
        
        if isinstance(sales_data, list) and sales_data:
            # Выводим первую строку для отладки
            if sales_data:
                logger.info(f"Sample raw sales data row keys: {list(sales_data[0].keys())}")
                logger.info(f"Sample raw sales data first row: {sales_data[0]}")
                
            for row in sales_data:
                # Проверка флагов для отмены чека
                dish_return_sum = None
                is_storned = False
                
                # Проверим на отмененный чек и возврат
                for key, value in row.items():
                    if key.endswith('DishReturnSum'):
                        try:
                            dish_return_sum = int(value) if value else 0
                        except (ValueError, TypeError):
                            dish_return_sum = 0
                    elif key.endswith('Storned') and value and value.upper() == 'TRUE':
                        is_storned = True
                
                # Пропускаем отмененные чеки и возвраты
                if is_storned:
                    logger.debug(f"Skipping storned check with flag Storned=TRUE")
                    skipped_storned += 1
                    continue
                
                if dish_return_sum and dish_return_sum > 0:
                    logger.debug(f"Skipping return item with DishReturnSum = {dish_return_sum}")
                    skipped_returns += 1
                    continue
                
                sale_item = {}
                store_name = None
                
                # Сначала найдем имя склада, проверяя все ключи
                for key, value in row.items():
                    if key.endswith('Store.Name'):
                        store_name = value
                        logger.info(f"Found Store.Name in key: {key} with value: {value}")
                        break
                
                # Теперь обработаем все поля
                for key, value in row.items():
                    # Удаляем префиксы с номерами колонок из OLAP результата
                    clean_key = key.split('.')[-1]  # Берем только часть после последней точки
                    
                    # Особые случаи
                    if key.endswith('CashRegisterName.Number'):
                        sale_item["CashRegisterName.Number"] = value
                    elif key.endswith('CashRegisterName.CashRegisterSerialNumber'):
                        sale_item["CashRegisterName.CashRegisterSerialNumber"] = value
                    elif key.endswith('Department.Id'):
                        sale_item["Department.Id"] = value
                    elif key.endswith('OrderIncrease.Type'):
                        sale_item["OrderIncrease.Type"] = value
                    else:
                        sale_item[clean_key] = value
                
                # Добавляем имя склада, если нашли
                if store_name:
                    sale_item["Store.Name"] = store_name
                formatted_sales.append(sale_item)
        
        logger.info(f"Загружено {len(formatted_sales)} записей о продажах")
        logger.info(f"Статистика фильтрации: пропущено отмененных чеков: {skipped_storned}, пропущено возвратов: {skipped_returns}")
        return formatted_sales
    
    def get_accounts(self, include_deleted: bool = False) -> list:
        """Получение списка счетов"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        accounts_url = f"{self.base_url}/v2/entities/accounts/list"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'includeDeleted': str(include_deleted).lower()
        }
        
        logger.info(f"Загрузка списка счетов...")
        
        response = requests.get(accounts_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        accounts_data = response.json()
        logger.info(f"Загружено {len(accounts_data)} счетов")
        
        return accounts_data
    
    def get_writeoff_documents(self, date_from=None, date_to=None) -> list:
        """Получение документов списания за период"""
        import logging
        from datetime import datetime, timedelta
        
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
        
        # Если даты не указаны, берем последний месяц
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
        writeoff_url = f"{self.base_url}/v2/documents/writeoff"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'dateFrom': date_from,
            'dateTo': date_to
        }
        
        logger.info(f"Загрузка документов списания с {date_from} по {date_to}...")
        
        response = requests.get(writeoff_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        response_data = response.json()
        
        # Проверяем структуру ответа
        if isinstance(response_data, dict) and 'response' in response_data:
            documents_data = response_data['response']
        else:
            documents_data = response_data
            
        logger.info(f"Загружено {len(documents_data)} документов списания")
        
        return documents_data
