#!/usr/bin/env python3
"""
Скрипт для проверки соответствия количества товаров в API и базе данных
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
from src.models import Product
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
        logger.info("Проверка соответствия номенклатуры между API и БД")
        
        # Данные из API
        logger.info("Получение данных из API...")
        api_products = api_client.get_products()
        api_total_count = len(api_products)
        
        # Подсчитываем активные и удаленные в API
        api_active_count = sum(1 for p in api_products if not p.get('deleted', False))
        api_deleted_count = sum(1 for p in api_products if p.get('deleted', False))
        
        logger.info(f"API: Всего = {api_total_count}, Активных = {api_active_count}, Удаленных = {api_deleted_count}")
        
        # Данные из БД
        logger.info("Получение данных из БД...")
        db_total_count = session.query(func.count(Product.id)).scalar() or 0
        db_active_count = session.query(func.count(Product.id)).filter(Product.deleted == False).scalar() or 0
        db_deleted_count = session.query(func.count(Product.id)).filter(Product.deleted == True).scalar() or 0
        
        logger.info(f"БД:  Всего = {db_total_count}, Активных = {db_active_count}, Удаленных = {db_deleted_count}")
        
        # Сравнение
        logger.info("=== РЕЗУЛЬТАТ СРАВНЕНИЯ ===")
        logger.info(f"Всего:     API = {api_total_count}, БД = {db_total_count}, Разница = {api_total_count - db_total_count}")
        logger.info(f"Активных:  API = {api_active_count}, БД = {db_active_count}, Разница = {api_active_count - db_active_count}")
        logger.info(f"Удаленных: API = {api_deleted_count}, БД = {db_deleted_count}, Разница = {api_deleted_count - db_deleted_count}")
        
        # Проверяем соответствие
        if api_total_count == db_total_count:
            logger.info("✅ Общее количество товаров соответствует!")
        else:
            logger.warning("⚠️  Общее количество товаров не соответствует!")
            
        if api_active_count == db_active_count:
            logger.info("✅ Количество активных товаров соответствует!")
        else:
            logger.warning("⚠️  Количество активных товаров не соответствует!")
            
        if api_deleted_count == db_deleted_count:
            logger.info("✅ Количество удаленных товаров соответствует!")
        else:
            logger.warning("⚠️  Количество удаленных товаров не соответствует!")
        
        # Дополнительная проверка на уникальные ID
        logger.info("\n=== ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА ===")
        
        # Получаем все ID из API
        api_ids = set(p.get('id') for p in api_products if p.get('id'))
        logger.info(f"Уникальных ID в API: {len(api_ids)}")
        
        # Получаем все ID из БД
        db_ids = set(str(row[0]) for row in session.query(Product.id).all())
        logger.info(f"Уникальных ID в БД: {len(db_ids)}")
        
        # Находим различия
        missing_in_db = api_ids - db_ids
        extra_in_db = db_ids - api_ids
        
        logger.info(f"Товаров в API, но нет в БД: {len(missing_in_db)}")
        logger.info(f"Товаров в БД, но нет в API: {len(extra_in_db)}")
        
        if missing_in_db:
            logger.info("Примеры товаров, отсутствующих в БД:")
            for i, product_id in enumerate(list(missing_in_db)[:5]):
                # Находим товар в API
                product = next((p for p in api_products if p.get('id') == product_id), None)
                if product:
                    logger.info(f"  {i+1}. ID: {product_id}, Название: {product.get('name', 'Без названия')}")
        
        if extra_in_db:
            logger.info("Примеры товаров, лишних в БД:")
            for i, product_id in enumerate(list(extra_in_db)[:5]):
                logger.info(f"  {i+1}. ID: {product_id}")
        
        # Проверяем коды товаров
        logger.info("\n=== ПРОВЕРКА КОДОВ ===")
        api_codes = set(p.get('code') for p in api_products if p.get('code') and p.get('code') != '')
        logger.info(f"Уникальных кодов в API: {len(api_codes)}")
        
        db_codes_count = session.query(func.count(Product.id)).filter(Product.code.isnot(None)).scalar() or 0
        logger.info(f"Товаров с кодами в БД: {db_codes_count}")
        
        # Последняя синхронизация
        from src.models import SyncLog
        last_sync = session.query(SyncLog).filter(SyncLog.entity_type == 'products').order_by(SyncLog.sync_date.desc()).first()
        if last_sync:
            logger.info(f"\nПоследняя синхронизация: {last_sync.sync_date}")
            logger.info(f"Статус: {last_sync.status}")
            if last_sync.details:
                details = last_sync.details
                logger.info(f"Создано: {details.get('created', 0)}, Обновлено: {details.get('updated', 0)}, Ошибок: {details.get('errors', 0)}")
        else:
            logger.warning("Синхронизация товаров никогда не запускалась!")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()

if __name__ == "__main__":
    main()