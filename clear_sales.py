#!/usr/bin/env python3
"""
Скрипт для очистки таблицы продаж
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Sale
from config.config import DATABASE_CONFIG
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def clear_sales():
    """Очистка всех продаж из базы данных"""
    
    # Подключение к базе данных
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Подсчет количества записей
        count = session.query(Sale).count()
        logger.info(f"Найдено {count} записей продаж для удаления")
        
        # Удаление всех записей
        session.query(Sale).delete()
        session.commit()
        
        logger.info(f"Успешно удалено {count} записей продаж")
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при очистке продаж: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("Начинаем очистку таблицы продаж...")
    success = clear_sales()
    if success:
        print("Таблица продаж успешно очищена")
    else:
        print("Произошла ошибка при очистке таблицы продаж")