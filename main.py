#!/usr/bin/env python3
"""
Основной скрипт для синхронизации данных из IIKO API в локальную БД
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.synchronizer import DataSynchronizer
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
    parser.add_argument('--entity', choices=['products', 'all'], default='all',
                      help='Какие сущности синхронизировать')
    parser.add_argument('--analyze', action='store_true',
                      help='Только проанализировать структуру данных')
    
    args = parser.parse_args()
    
    try:
        synchronizer = DataSynchronizer()
        
        if args.analyze:
            logger.info("Анализ структуры данных...")
            from src.api_client import IIKOApiClient
            client = IIKOApiClient()
            structure = client.analyze_products_structure()
            logger.info(f"Структура: {structure}")
        else:
            if args.entity in ['products', 'all']:
                logger.info("Синхронизация продуктов...")
                synchronizer.sync_products()
                
            logger.info("Синхронизация завершена успешно")
            
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise

if __name__ == "__main__":
    # Создаем директорию для логов
    os.makedirs('logs', exist_ok=True)
    main()
