import os
import sys
import logging
from datetime import datetime, timedelta
from collections import defaultdict

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_detailed_check")

# Добавляем путь проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import Base, Sale
from config.config import DATABASE_CONFIG

def test_check_uniqueness():
    """
    Тест для проверки уникальности в разрезе номера чека, товара и номера кассы
    """
    # Период для тестирования (1 день для упрощения анализа)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    from_date = datetime.strptime(start_date, '%Y-%m-%d')
    to_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    
    logger.info(f"Анализ данных продаж с {start_date} по {end_date}")
    
    # Подключение к базе данных
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Получаем данные о продажах из API
        api_client = IikoApiClient()
        sales_data = api_client.get_sales(start_date, end_date)
        
        logger.info(f"Получено {len(sales_data)} записей через API")
        
        # Анализируем данные из API
        api_check_counts = defaultdict(int)
        api_product_counts = defaultdict(int)
        api_unique_keys = set()
        
        for item in sales_data:
            order_num = item.get("OrderNum")
            fiscal_cheque_number = item.get("FiscalChequeNumber")
            dish_code = item.get("DishCode")
            cash_register_number = item.get("CashRegisterName.Number")
            
            # Считаем количество позиций по чекам
            check_key = f"{order_num}_{fiscal_cheque_number}"
            api_check_counts[check_key] += 1
            
            # Считаем количество одинаковых товаров
            product_key = f"{order_num}_{fiscal_cheque_number}_{dish_code}"
            api_product_counts[product_key] += 1
            
            # Уникальный ключ (чек + товар + касса)
            unique_key = f"{order_num}_{fiscal_cheque_number}_{dish_code}_{cash_register_number}"
            api_unique_keys.add(unique_key)
        
        # Считаем статистику по API данным
        num_checks = len(api_check_counts)
        multi_position_checks = sum(1 for count in api_check_counts.values() if count > 1)
        avg_positions = sum(api_check_counts.values()) / num_checks if num_checks > 0 else 0
        
        logger.info(f"API статистика:")
        logger.info(f"Уникальных чеков: {num_checks}")
        logger.info(f"Чеков с несколькими позициями: {multi_position_checks} ({multi_position_checks/num_checks*100:.1f}%)")
        logger.info(f"Среднее количество позиций в чеке: {avg_positions:.2f}")
        logger.info(f"Уникальных комбинаций (чек+товар+касса): {len(api_unique_keys)}")
        
        # Проверяем БД
        db_sales = session.query(Sale).filter(
            Sale.close_time >= from_date,
            Sale.close_time < to_date
        ).all()
        
        logger.info(f"Получено {len(db_sales)} записей из базы данных")
        
        # Анализируем данные из БД
        db_check_counts = defaultdict(int)
        db_product_counts = defaultdict(int)
        db_unique_keys = set()
        
        for sale in db_sales:
            order_num = sale.order_num
            fiscal_cheque_number = sale.fiscal_cheque_number
            dish_code = sale.dish_code
            cash_register_number = sale.cash_register_number
            
            # Считаем количество позиций по чекам
            check_key = f"{order_num}_{fiscal_cheque_number}"
            db_check_counts[check_key] += 1
            
            # Считаем количество одинаковых товаров
            product_key = f"{order_num}_{fiscal_cheque_number}_{dish_code}"
            db_product_counts[product_key] += 1
            
            # Уникальный ключ (чек + товар + касса)
            unique_key = f"{order_num}_{fiscal_cheque_number}_{dish_code}_{cash_register_number}"
            db_unique_keys.add(unique_key)
        
        # Считаем статистику по БД данным
        db_num_checks = len(db_check_counts)
        db_multi_position_checks = sum(1 for count in db_check_counts.values() if count > 1)
        db_avg_positions = sum(db_check_counts.values()) / db_num_checks if db_num_checks > 0 else 0
        
        logger.info(f"БД статистика:")
        logger.info(f"Уникальных чеков: {db_num_checks}")
        logger.info(f"Чеков с несколькими позициями: {db_multi_position_checks} ({db_multi_position_checks/db_num_checks*100:.1f}%)")
        logger.info(f"Среднее количество позиций в чеке: {db_avg_positions:.2f}")
        logger.info(f"Уникальных комбинаций (чек+товар+касса): {len(db_unique_keys)}")
        
        # Проверяем соответствие ключей
        api_only_keys = api_unique_keys - db_unique_keys
        db_only_keys = db_unique_keys - api_unique_keys
        common_keys = api_unique_keys.intersection(db_unique_keys)
        
        logger.info(f"Сравнение данных:")
        logger.info(f"Общих уникальных ключей: {len(common_keys)}")
        logger.info(f"Ключей только в API: {len(api_only_keys)}")
        logger.info(f"Ключей только в БД: {len(db_only_keys)}")
        
        # Если есть расхождения, выведем детали для первых 5 ключей
        if api_only_keys:
            logger.info(f"Примеры ключей только в API (первые 5):")
            for i, key in enumerate(list(api_only_keys)[:5]):
                logger.info(f"  {i+1}. {key}")
                
        if db_only_keys:
            logger.info(f"Примеры ключей только в БД (первые 5):")
            for i, key in enumerate(list(db_only_keys)[:5]):
                logger.info(f"  {i+1}. {key}")
                
        # Проверка уникальности записей в БД
        from sqlalchemy import text
        
        unique_constraint_check = text("""
        WITH duplicates AS (
            SELECT 
                order_num, 
                fiscal_cheque_number, 
                dish_code, 
                cash_register_number, 
                COUNT(*) as count
            FROM 
                sales
            WHERE 
                close_time >= :from_date AND close_time < :to_date
            GROUP BY 
                order_num, fiscal_cheque_number, dish_code, cash_register_number
            HAVING 
                COUNT(*) > 1
        )
        SELECT COUNT(*) FROM duplicates;
        """)
        
        duplicate_count = session.execute(
            unique_constraint_check, 
            {"from_date": from_date, "to_date": to_date}
        ).scalar()
        
        logger.info(f"Количество дубликатов в БД по ключу (order_num, fiscal_cheque_number, dish_code, cash_register_number): {duplicate_count}")
        
        # Если есть дубликаты, выведем первые 5
        if duplicate_count > 0:
            duplicates_query = text("""
            WITH duplicates AS (
                SELECT 
                    order_num, 
                    fiscal_cheque_number, 
                    dish_code, 
                    cash_register_number, 
                    COUNT(*) as count
                FROM 
                    sales
                WHERE 
                    close_time >= :from_date AND close_time < :to_date
                GROUP BY 
                    order_num, fiscal_cheque_number, dish_code, cash_register_number
                HAVING 
                    COUNT(*) > 1
            )
            SELECT order_num, fiscal_cheque_number, dish_code, cash_register_number, count 
            FROM duplicates
            ORDER BY count DESC
            LIMIT 5;
            """)
            
            duplicates = session.execute(
                duplicates_query, 
                {"from_date": from_date, "to_date": to_date}
            ).fetchall()
            
            logger.info(f"Топ 5 дубликатов:")
            for i, dup in enumerate(duplicates):
                logger.info(f"  {i+1}. Чек {dup[0]}_{dup[1]}, товар {dup[2]}, касса {dup[3]} - {dup[4]} записей")
                
    finally:
        session.close()
    
if __name__ == "__main__":
    test_check_uniqueness()