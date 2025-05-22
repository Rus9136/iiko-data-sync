import os
import sys
import logging
from datetime import datetime, timedelta

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_detailed_sales")

# Добавляем путь проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
from src.models import Base, Sale
from config.config import DATABASE_CONFIG

def test_sales_filters():
    """
    Тест фильтрации продаж
    """
    # Подключение к базе данных
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Период для тестирования (последние 3 дня)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    from_date = datetime.strptime(start_date, '%Y-%m-%d')
    to_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    
    logger.info(f"Анализ продаж по фильтрам для периода с {start_date} по {end_date}")
    
    # Получаем информацию о продажах по флагам DeletedWithWriteoff 
    for status in ["NOT_DELETED", "DELETED_WITH_WRITEOFF", "DELETED_WITHOUT_WRITEOFF"]:
        count = session.query(func.count(Sale.id)).filter(
            Sale.close_time >= from_date,
            Sale.close_time < to_date,
            Sale.deleted_with_writeoff == status
        ).scalar() or 0
        
        logger.info(f"Продажи с флагом DeletedWithWriteoff={status}: {count}")
    
    # Проверяем, есть ли продажи с DishReturnSum > 0
    return_count = session.query(func.count(Sale.id)).filter(
        Sale.close_time >= from_date,
        Sale.close_time < to_date,
        Sale.dish_return_sum > 0
    ).scalar() or 0
    
    logger.info(f"Продажи с DishReturnSum > 0: {return_count}")
    
    # Анализ исходных данных API
    api_client = IikoApiClient()
    
    # Вызываем метод API, но без встроенных фильтров, чтобы увидеть все данные
    # Временно изменим метод и параметры для тестирования
    original_method = api_client.get_sales
    
    def test_get_sales(self, start_date=None, end_date=None):
        """Временная версия метода для тестирования - получаем все данные без фильтрации"""
        from datetime import datetime, timedelta
        import logging
        
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
        
        sales_url = f"{self.base_url}/v2/reports/olap"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        params = {
            'key': self.token
        }
        
        # Формируем тело запроса в соответствии с OLAP API, без фильтров
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
                "Storned"
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
                }
                # Убираем все остальные фильтры, чтобы получить все данные
            }
        }
        
        logger.info(f"Загрузка продаж с {start_date} по {end_date} без фильтрации")
        
        import requests
        response = requests.post(sales_url, params=params, headers=headers, json=request_body)
        response_status = response.status_code
        logger.info(f"Получен ответ от API со статусом: {response_status}")
        
        response.raise_for_status()
        
        sales_data = response.json()
        
        if isinstance(sales_data, dict) and 'data' in sales_data:
            sales_data = sales_data['data']
        
        # Обработка данных без фильтрации
        formatted_sales = []
        deleted_count = 0
        deleted_with_writeoff_count = 0
        deleted_without_writeoff_count = 0
        not_deleted_count = 0
        storned_true_count = 0
        storned_false_count = 0
        dish_return_positive_count = 0
        
        if isinstance(sales_data, list) and sales_data:
            for row in sales_data:
                # Подсчет статистики по флагам
                for key, value in row.items():
                    if key.endswith('DeletedWithWriteoff'):
                        if value == "DELETED_WITH_WRITEOFF":
                            deleted_with_writeoff_count += 1
                        elif value == "DELETED_WITHOUT_WRITEOFF":
                            deleted_without_writeoff_count += 1
                        elif value == "NOT_DELETED":
                            not_deleted_count += 1
                    
                    if key.endswith('Storned'):
                        if value and value.upper() == "TRUE":
                            storned_true_count += 1
                        else:
                            storned_false_count += 1
                    
                    if key.endswith('DishReturnSum'):
                        try:
                            return_sum = int(value) if value else 0
                            if return_sum > 0:
                                dish_return_positive_count += 1
                        except (ValueError, TypeError):
                            pass
        
        logger.info(f"Общее количество записей с API: {len(sales_data)}")
        logger.info(f"Статистика по DeletedWithWriteoff:")
        logger.info(f"  DELETED_WITH_WRITEOFF: {deleted_with_writeoff_count}")
        logger.info(f"  DELETED_WITHOUT_WRITEOFF: {deleted_without_writeoff_count}")
        logger.info(f"  NOT_DELETED: {not_deleted_count}")
        logger.info(f"Статистика по Storned:")
        logger.info(f"  TRUE: {storned_true_count}")
        logger.info(f"  FALSE: {storned_false_count}")
        logger.info(f"Продажи с DishReturnSum > 0: {dish_return_positive_count}")
        
        return sales_data
    
    # Подменяем метод для тестирования
    api_client.get_sales = test_get_sales.__get__(api_client)
    
    try:
        # Запускаем тестовый метод
        api_client.get_sales(start_date, end_date)
    finally:
        # Восстанавливаем оригинальный метод
        api_client.get_sales = original_method.__get__(api_client)
    
    session.close()
    
if __name__ == "__main__":
    test_sales_filters()