#!/usr/bin/env python3
"""
Основной скрипт для синхронизации данных из IIKO API в локальную БД
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.synchronizer import DataSynchronizer
from src.store_synchronizer import StoreSynchronizer
from src.sales_synchronizer import SalesSynchronizer
from src.department_synchronizer import DepartmentSynchronizer
import argparse
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='IIKO Data Synchronizer')
    parser.add_argument('--entity', choices=['products', 'stores', 'sales', 'accounts', 'writeoffs', 'departments', 'prices', 'all'], default='all',
                      help='Какие сущности синхронизировать')
    parser.add_argument('--start-date', help='Начальная дата для продаж в формате YYYY-MM-DD')
    parser.add_argument('--end-date', help='Конечная дата для продаж в формате YYYY-MM-DD')
    parser.add_argument('--department-id', help='ID подразделения для синхронизации цен')
    parser.add_argument('--price-type', default='BASE', help='Тип цен для синхронизации (по умолчанию BASE)')
    parser.add_argument('--analyze', action='store_true',
                      help='Только проанализировать структуру данных')
    
    args = parser.parse_args()
    
    try:
        synchronizer = DataSynchronizer()
        
        if args.analyze:
            logger.info("Анализ структуры данных...")
            from src.api_client import IikoApiClient
            client = IikoApiClient()
            structure = client.analyze_products_structure()
            logger.info(f"Структура: {structure}")
        else:
            if args.entity in ['products', 'all']:
                logger.info("Синхронизация продуктов...")
                synchronizer.sync_products()
            
            if args.entity in ['stores', 'all']:
                logger.info("Синхронизация складов...")
                store_synchronizer = StoreSynchronizer()
                store_synchronizer.sync_stores()
                
            if args.entity in ['sales', 'all']:
                logger.info("Синхронизация продаж...")
                sales_synchronizer = SalesSynchronizer()
                sales_synchronizer.sync_sales(args.start_date, args.end_date)
            
            if args.entity in ['accounts', 'all']:
                logger.info("Синхронизация счетов...")
                synchronizer.sync_accounts()
            
            if args.entity in ['writeoffs', 'all']:
                logger.info("Синхронизация документов списания...")
                synchronizer.sync_writeoff_documents(args.start_date, args.end_date)
            
            if args.entity in ['departments', 'all']:
                logger.info("Синхронизация подразделений...")
                from src.api_client import IikoApiClient
                from config.config import CONNECTION_STRING
                api_client = IikoApiClient()
                dept_synchronizer = DepartmentSynchronizer(api_client, CONNECTION_STRING)
                dept_synchronizer.sync_departments()
            
            if args.entity == 'prices':
                if not args.department_id:
                    logger.error("Для синхронизации цен необходимо указать --department-id")
                    return
                    
                logger.info(f"Синхронизация цен для подразделения {args.department_id}...")
                from src.api_client import IikoApiClient
                from src.price_synchronizer import PriceSynchronizer
                from config.config import CONNECTION_STRING
                
                # Используем даты по умолчанию если не указаны
                start_date = args.start_date or "2025-01-01"
                end_date = args.end_date or "2025-12-31"
                
                api_client = IikoApiClient()
                price_synchronizer = PriceSynchronizer(api_client, CONNECTION_STRING)
                price_synchronizer.sync_prices(args.department_id, start_date, end_date, args.price_type)
                
            logger.info("Синхронизация завершена успешно")
            
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise

if __name__ == "__main__":
    # Создаем директорию для логов
    os.makedirs('logs', exist_ok=True)
    main()
