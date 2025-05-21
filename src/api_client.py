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
        """Получение списка продуктов с поддержкой пагинации"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        products_url = f"{self.base_url}/v2/entities/products/list"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        all_products = []
        page = 0
        page_size = 4000  # Оптимальный размер страницы
        has_more = True
        total_fetched = 0
        
        logger.info(f"Начинаем загрузку продуктов с пагинацией (размер страницы: {page_size})...")
        
        while has_more:
            params = {
                'includeDeleted': str(include_deleted).lower(),
                'pageSize': page_size,
                'page': page
            }
            
            logger.info(f"Загрузка страницы {page}...")
            
            response = requests.get(products_url, params=params, headers=headers)
            response_status = response.status_code
            logger.info(f"Получен ответ от API со статусом: {response_status}")
            
            response.raise_for_status()
            
            products_page = response.json()
            if not products_page:
                logger.info(f"Получена пустая страница {page}, завершаем загрузку")
                break
                
            total_fetched += len(products_page)
            logger.info(f"Загружено {len(products_page)} продуктов со страницы {page}, всего: {total_fetched}")
            
            # Сохраняем подробные данные о каждой странице
            logger.info(f"Данные страницы {page}: первый ID={products_page[0]['id'] if products_page else 'Н/Д'}, "
                         f"последний ID={products_page[-1]['id'] if products_page else 'Н/Д'}")
            
            # Расширяем общий список
            all_products.extend(products_page)
            
            # Проверяем, есть ли еще страницы
            if len(products_page) < page_size:
                logger.info(f"Достигнут конец списка продуктов (получено {len(products_page)} из {page_size})")
                has_more = False
            elif page >= 5:  # Ограничиваем максимальное количество страниц для тестирования
                logger.info(f"Достигнут лимит пагинации (5 страниц)")
                has_more = False
            else:
                page += 1
        
        # Проверка на различие между количеством страниц и общим количеством
        if total_fetched != len(all_products):
            logger.warning(f"ВНИМАНИЕ! Несоответствие в подсчете: всего загружено {total_fetched}, "
                           f"но в списке {len(all_products)} продуктов")
        
        logger.info(f"Загрузка завершена. Всего загружено {len(all_products)} продуктов")        
        return all_products
    
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
                "OrderIncrease.Type"
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
                        "NOT_DELETED", 
                        "DELETED_WITH_WRITEOFF", 
                        "DELETED_WITHOUT_WRITEOFF"
                    ]
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
        if isinstance(sales_data, list) and sales_data:
            for row in sales_data:
                sale_item = {}
                for key, value in row.items():
                    # Удаляем префиксы с номерами колонок из OLAP результата
                    clean_key = key.split('.')[-1]  # Берем только часть после последней точки
                    # Сохраняем полные ключи для специальных полей
                    if key in ["CashRegisterName.Number", "CashRegisterName.CashRegisterSerialNumber", 
                              "Department.Id", "OrderIncrease.Type"]:
                        sale_item[key] = value
                    else:
                        sale_item[clean_key] = value
                formatted_sales.append(sale_item)
        
        logger.info(f"Загружено {len(formatted_sales)} записей о продажах")
        return formatted_sales
