import os
import sys
import logging
from datetime import datetime, timedelta

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_sync_count")

# Добавляем путь проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.sales_synchronizer import SalesSynchronizer
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import Base, Sale
from config.config import DATABASE_CONFIG

def test_sync_count():
    """
    Тест для проверки соответствия количества загруженных чеков
    """
    # Период для тестирования (последние 3 дня)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    from_date = datetime.strptime(start_date, '%Y-%m-%d')
    to_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    
    logger.info(f"Тестирование синхронизации продаж с {start_date} по {end_date}")
    
    # Очищаем существующие данные за период
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Очистка данных
        from sqlalchemy import and_
        deleted_count = session.query(Sale).filter(
            and_(Sale.close_time >= from_date, Sale.close_time < to_date)
        ).delete(synchronize_session=False)
        
        session.commit()
        logger.info(f"Очищено {deleted_count} записей о продажах за период")
        
        # Подсчет количества продаж
        before_count = session.query(func.count(Sale.id)).filter(
            and_(Sale.close_time >= from_date, Sale.close_time < to_date)
        ).scalar() or 0
        
        logger.info(f"Количество продаж перед синхронизацией: {before_count}")
        
        # Запускаем синхронизацию
        synchronizer = SalesSynchronizer()
        synchronizer.sync_sales(start_date, end_date, clear_existing=True)
        
        # Подсчет после синхронизации
        after_count = session.query(func.count(Sale.id)).filter(
            and_(Sale.close_time >= from_date, Sale.close_time < to_date)
        ).scalar() or 0
        
        logger.info(f"Количество продаж после синхронизации: {after_count}")
        logger.info(f"Статистика синхронизации: {synchronizer.stats}")
        
        # Подсчет уникальных чеков
        unique_orders = session.query(func.count(func.distinct(Sale.order_num))).filter(
            and_(Sale.close_time >= from_date, Sale.close_time < to_date)
        ).scalar() or 0
        
        logger.info(f"Количество уникальных номеров заказов: {unique_orders}")
        
        # Подсчет по полю deleted_with_writeoff
        not_deleted = session.query(func.count(Sale.id)).filter(
            and_(Sale.close_time >= from_date, Sale.close_time < to_date, Sale.deleted_with_writeoff == "NOT_DELETED")
        ).scalar() or 0
        
        logger.info(f"Количество чеков с deleted_with_writeoff=NOT_DELETED: {not_deleted}")
        
    finally:
        session.close()
    
if __name__ == "__main__":
    test_sync_count()