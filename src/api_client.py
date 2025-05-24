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
            
        # IIKO требует, чтобы конечная дата была больше начальной
        # Если даты совпадают, добавляем один день к конечной дате
        if start_date == end_date:
            from datetime import datetime as dt
            end_date_obj = dt.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            end_date = end_date_obj.strftime('%Y-%m-%d')
        
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
        logger.debug(f"Request body: {json.dumps(request_body, indent=2)}")
        
        response = requests.post(sales_url, params=params, headers=headers, json=request_body)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        if response.status_code == 409:
            logger.error(f"API returned 409 Conflict. Response: {response.text}")
        
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
    
    def get_prices(self, department_id: str, date_from: str, date_to: str, price_type: str = 'BASE') -> dict:
        """Получение цен для подразделения за период"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        prices_url = f"{self.base_url}/v2/price"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'dateFrom': date_from,
            'dateTo': date_to,
            'type': price_type,
            'departmentId': department_id
        }
        
        logger.info(f"Загрузка цен для подразделения {department_id} с {date_from} по {date_to}, тип: {price_type}")
        
        response = requests.get(prices_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('result') != 'SUCCESS':
            errors = data.get('errors', [])
            error_msg = '; '.join(errors) if errors else 'Unknown error'
            raise Exception(f"API error: {error_msg}")
        
        prices_data = data.get('response', [])
        logger.info(f"Загружено {len(prices_data)} записей о ценах")
        
        return prices_data
    
    def get_suppliers(self) -> list:
        """Получение списка поставщиков из API"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        suppliers_url = f"{self.base_url}/suppliers"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'key': self.token
        }
        
        logger.info(f"Загрузка списка поставщиков...")
        
        response = requests.get(suppliers_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        # Парсим XML ответ
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        
        suppliers = []
        for employee in root.findall('.//employee'):
            # Берем только тех, кто является поставщиком
            is_supplier = employee.find('supplier')
            if is_supplier is not None and is_supplier.text == 'true':
                supplier = {
                    'id': employee.find('id').text if employee.find('id') is not None else None,
                    'code': employee.find('code').text if employee.find('code') is not None else None,
                    'name': employee.find('name').text if employee.find('name') is not None else None,
                    'login': employee.find('login').text if employee.find('login') is not None else None,
                    'cardNumber': employee.find('cardNumber').text if employee.find('cardNumber') is not None else None,
                    'taxpayerIdNumber': employee.find('taxpayerIdNumber').text if employee.find('taxpayerIdNumber') is not None else None,
                    'snils': employee.find('snils').text if employee.find('snils') is not None else None,
                    'deleted': employee.find('deleted').text == 'true' if employee.find('deleted') is not None else False,
                    'supplier': employee.find('supplier').text == 'true' if employee.find('supplier') is not None else False,
                    'employee': employee.find('employee').text == 'true' if employee.find('employee') is not None else False,
                    'client': employee.find('client').text == 'true' if employee.find('client') is not None else False,
                    'representsStore': employee.find('representsStore').text == 'true' if employee.find('representsStore') is not None else False
                }
                suppliers.append(supplier)
        
        logger.info(f"Загружено {len(suppliers)} поставщиков")
        return suppliers
    
    def get_departments(self) -> list:
        """Получение списка подразделений из API"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        departments_url = f"{self.base_url}/corporation/departments"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        params = {
            'key': self.token,
            'revisionFrom': '-1'
        }
        
        logger.info(f"Загрузка списка подразделений...")
        
        response = requests.get(departments_url, params=params, headers=headers)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        # Парсим XML ответ
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        
        departments = []
        for item in root.findall('.//corporateItemDto'):
            department = {
                'id': item.find('id').text if item.find('id') is not None else None,
                'parentId': item.find('parentId').text if item.find('parentId') is not None else None,
                'code': item.find('code').text if item.find('code') is not None else None,
                'name': item.find('name').text if item.find('name') is not None else None,
                'type': item.find('type').text if item.find('type') is not None else 'DEPARTMENT',
                'taxpayerIdNumber': item.find('taxpayerIdNumber').text if item.find('taxpayerIdNumber') is not None else None
            }
            departments.append(department)
        
        logger.info(f"Загружено {len(departments)} подразделений")
        return departments
    
    def get_writeoff_documents(self, date_from=None, date_to=None) -> list:
        """Получение документов списания за период с фильтрацией по статусам NEW и PROCESSED"""
        import logging
        from datetime import datetime, timedelta
        
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
        
        # Если даты не указаны, берем вчерашний день для тестирования
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
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
            
        logger.info(f"Всего получено {len(documents_data)} документов списания")
        
        # Сначала проанализируем статусы, которые приходят из API
        status_counts = {}
        for doc in documents_data:
            status = doc.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            logger.info(f"Статусы документов из API: {status_counts}")
        
        # Фильтруем документы только со статусами NEW и PROCESSED
        allowed_statuses = ['NEW', 'PROCESSED']
        filtered_documents = []
        
        for doc in documents_data:
            doc_status = doc.get('status', '')
            if doc_status in allowed_statuses:
                filtered_documents.append(doc)
            else:
                logger.debug(f"Пропущен документ {doc.get('documentNumber', 'без номера')} со статусом {doc_status}")
        
        logger.info(f"После фильтрации по статусам ({', '.join(allowed_statuses)}) осталось {len(filtered_documents)} документов")
        
        return filtered_documents
