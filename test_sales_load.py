import os
import sys
import logging
from datetime import datetime, timedelta

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_sales_load")

# Добавляем путь проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
from src.sales_synchronizer import SalesSynchronizer
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import Base, Sale
from config.config import DATABASE_CONFIG

def test_sales_load():
    """
    Тест загрузки продаж за определенный период.
    Проверяет количество загруженных чеков и сравнивает с количеством в базе данных.
    """
    # Период для тестирования (последние 3 дня)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    logger.info(f"Тестирование загрузки продаж с {start_date} по {end_date}")
    
    # Получаем данные непосредственно через API клиент
    api_client = IikoApiClient()
    raw_sales = api_client.get_sales(start_date, end_date)
    
    logger.info(f"Получено через API: {len(raw_sales)} чеков")
    
    # Подключение к базе данных для проверки текущего количества продаж
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Проверяем текущее количество записей за выбранный период
    from_date = datetime.strptime(start_date, '%Y-%m-%d')
    to_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Добавляем день для включения всего дня end_date
    
    existing_count = session.query(func.count(Sale.id)).filter(
        Sale.close_time >= from_date,
        Sale.close_time < to_date
    ).scalar() or 0
    
    logger.info(f"Текущее количество продаж в базе за период: {existing_count}")
    
    # Запускаем синхронизацию
    synchronizer = SalesSynchronizer()
    logger.info("Запуск синхронизации продаж")
    synchronizer.sync_sales(start_date, end_date, clear_existing=True)
    
    # Проверяем количество загруженных записей после синхронизации
    new_count = session.query(func.count(Sale.id)).filter(
        Sale.close_time >= from_date,
        Sale.close_time < to_date
    ).scalar() or 0
    
    logger.info(f"Количество продаж в базе после синхронизации: {new_count}")
    logger.info(f"Статистика синхронизации: {synchronizer.stats}")
    
    # Проверка соответствия
    if new_count == len(raw_sales):
        logger.info("ТЕСТ УСПЕШЕН: Количество чеков соответствует полученным через API")
    else:
        logger.warning(f"ТЕСТ НЕ ПРОШЕЛ: Количество чеков в базе ({new_count}) не соответствует полученным через API ({len(raw_sales)})")
    
    # Разбивка по статусам
    not_deleted_count = session.query(func.count(Sale.id)).filter(
        Sale.close_time >= from_date,
        Sale.close_time < to_date,
        Sale.deleted_with_writeoff == "NOT_DELETED"
    ).scalar() or 0
    
    storned_count = session.query(func.count(Sale.id)).filter(
        Sale.close_time >= from_date,
        Sale.close_time < to_date,
        Sale.storned == True
    ).scalar() or 0
    
    logger.info(f"Чеки NOT_DELETED: {not_deleted_count}")
    logger.info(f"Чеки STORNED=TRUE: {storned_count}")
    
    session.close()
    
if __name__ == "__main__":
    test_sales_load()