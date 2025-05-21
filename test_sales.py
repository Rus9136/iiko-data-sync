#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timedelta

from src.sales_synchronizer import SalesSynchronizer
from src.models import Sale
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.config import DATABASE_CONFIG

def test_sales_api():
    """Тестирование получения данных о продажах из API"""
    from src.api_client import IikoApiClient
    
    print("Тестирование API продаж...")
    client = IikoApiClient()
    
    # Получаем последние 7 дней
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    print(f"Запрос продаж с {start_date} по {end_date}")
    
    try:
        sales = client.get_sales(start_date, end_date)
        print(f"Получено {len(sales)} записей о продажах")
        
        # Выводим первые 3 записи для примера
        if sales:
            print("\nПримеры записей:")
            for i, sale in enumerate(sales[:3]):
                print(f"\nЗапись #{i+1}:")
                for key, value in sale.items():
                    print(f"  {key}: {value}")
                    
        return True
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return False

def test_sales_sync(start_date=None, end_date=None):
    """Тестирование синхронизации продаж"""
    print("Тестирование синхронизации продаж...")
    
    if start_date and end_date:
        print(f"Указан диапазон дат: с {start_date} по {end_date}")
    else:
        print("Диапазон дат не указан, будут использованы последние 7 дней")
    
    try:
        synchronizer = SalesSynchronizer()
        result = synchronizer.sync_sales(start_date, end_date)
        
        if result:
            print("Синхронизация выполнена успешно")
            print(f"Статистика: {synchronizer.stats}")
            
            # Проверяем, загрузились ли данные
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
            
            sales_count = session.query(Sale).count()
            print(f"Всего записей в таблице продаж: {sales_count}")
            
            if sales_count > 0:
                # Выводим несколько записей
                recent_sales = session.query(Sale).order_by(Sale.created_at.desc()).limit(3).all()
                print("\nПоследние добавленные записи:")
                for i, sale in enumerate(recent_sales):
                    print(f"\nЗапись #{i+1}:")
                    print(f"  ID: {sale.id}")
                    print(f"  Номер заказа: {sale.order_num}")
                    print(f"  Номер чека: {sale.fiscal_cheque_number}")
                    print(f"  Товар: {sale.dish_name}")
                    print(f"  Сумма: {sale.dish_sum}")
                    print(f"  Дата закрытия: {sale.close_time}")
            
            session.close()
            return True
        else:
            print("Синхронизация завершилась с ошибкой")
            return False
            
    except Exception as e:
        print(f"Ошибка при синхронизации: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Тестирование API и синхронизации продаж")
    parser.add_argument('--api', action='store_true', help='Тестировать только API')
    parser.add_argument('--sync', action='store_true', help='Тестировать только синхронизацию')
    parser.add_argument('--start-date', help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--end-date', help='Конечная дата в формате YYYY-MM-DD')
    
    args = parser.parse_args()
    
    # Если не указано ни одного флага, выполняем оба теста
    if not args.api and not args.sync:
        args.api = True
        args.sync = True
    
    if args.api:
        print("\n=== Тестирование API ===\n")
        test_sales_api()
        
    if args.sync:
        print("\n=== Тестирование синхронизации ===\n")
        test_sales_sync(args.start_date, args.end_date)