#!/usr/bin/env python3
"""
Скрипт для проверки соответствия количества документов списания в API и базе данных
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
from src.models import WriteoffDocument, WriteoffItem
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from config.config import DATABASE_CONFIG
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Подключение к БД
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Инициализация API клиента
    api_client = IikoApiClient()
    
    try:
        # Получаем данные из API за один день
        start_date = "2025-05-20"
        end_date = "2025-05-21"
        
        logger.info(f"Проверка соответствия данных за период {start_date} - {end_date}")
        
        # Данные из API
        api_documents = api_client.get_writeoff_documents(start_date, end_date)
        api_doc_count = len(api_documents)
        
        # Подсчитываем общее количество позиций в API
        api_items_count = 0
        for doc in api_documents:
            api_items_count += len(doc.get('items', []))
        
        logger.info(f"API: Документов = {api_doc_count}, Позиций = {api_items_count}")
        
        # Данные из БД
        db_doc_count = session.query(func.count(WriteoffDocument.id)).scalar()
        db_items_count = session.query(func.count(WriteoffItem.id)).scalar()
        
        logger.info(f"БД:  Документов = {db_doc_count}, Позиций = {db_items_count}")
        
        # Сравнение
        logger.info("=== РЕЗУЛЬТАТ СРАВНЕНИЯ ===")
        logger.info(f"Документы: API = {api_doc_count}, БД = {db_doc_count}, Разница = {api_doc_count - db_doc_count}")
        logger.info(f"Позиции:   API = {api_items_count}, БД = {db_items_count}, Разница = {api_items_count - db_items_count}")
        
        if api_doc_count == db_doc_count:
            logger.info("✅ Количество документов соответствует!")
        else:
            logger.warning("⚠️  Количество документов не соответствует!")
            
        # Проверяем причины расхождений позиций
        if api_items_count != db_items_count:
            logger.info("\n=== АНАЛИЗ ОШИБОК ===")
            logger.info("Расхождение в позициях может быть вызвано ссылками на несуществующие товары.")
            
            # Проверяем товары
            from src.models import Product
            product_count = session.query(func.count(Product.id)).scalar()
            logger.info(f"Товаров в БД: {product_count}")
            
            if product_count == 0:
                logger.warning("В базе данных нет товаров! Необходимо сначала синхронизировать номенклатуру.")
                logger.info("Запустите: python main.py --entity products")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке: {e}")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()