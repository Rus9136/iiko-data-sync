import sys
sys.path.append('/Users/rus/Projects/iiko-data-sync')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from src.models import Base, Store, SyncLog, StoreType
from src.api_client import IikoApiClient
from config.config import DATABASE_CONFIG
import logging

logger = logging.getLogger(__name__)

class StoreSynchronizer:
    def __init__(self):
        # Создаем подключение к БД
        db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Клиент API
        self.api_client = IikoApiClient()
        
        # Счетчики для отчетности
        self.counters = {
            'created': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def sync_stores(self):
        """Синхронизация складов из API в БД"""
        try:
            logger.info("Начинаем синхронизацию складов...")
            self.counters = {'created': 0, 'updated': 0, 'errors': 0, 'skipped': 0}
            
            # Очистка таблицы складов перед синхронизацией
            try:
                logger.info("Очистка таблицы складов перед синхронизацией...")
                store_count = self.session.query(Store).count()
                logger.info(f"Текущее количество складов в БД: {store_count}")
                self.session.query(Store).delete()
                self.session.commit()
                logger.info("Таблица складов успешно очищена")
            except Exception as e:
                self.session.rollback()
                logger.error(f"Ошибка при очистке таблицы складов: {e}")
                raise
            
            # Получаем данные из API
            stores_data = self.api_client.get_stores()
            logger.info(f"Получено {len(stores_data)} складов из API")
            
            # Добавляем отладочную информацию о первых и последних складах
            if stores_data:
                first_stores = stores_data[:5]
                last_stores = stores_data[-5:]
                
                logger.info("Первые 5 складов из API:")
                for i, s in enumerate(first_stores):
                    logger.info(f"  {i+1}. ID: {s.get('id')}, Название: {s.get('name')}, Тип: {s.get('type')}")
                    
                logger.info("Последние 5 складов из API:")
                for i, s in enumerate(last_stores):
                    logger.info(f"  {i+1}. ID: {s.get('id')}, Название: {s.get('name')}, Тип: {s.get('type')}")
            else:
                logger.warning("Получен пустой список складов из API!")
            
            # Процесс обработки каждого склада из API
            for store_data in stores_data:
                try:
                    self._sync_single_store(store_data)
                except Exception as e:
                    logger.error(f"Ошибка при синхронизации склада {store_data.get('id')}: {e}")
                    self.counters['errors'] += 1
                    self.session.rollback()
            
            # Записываем в лог
            sync_log = SyncLog(
                entity_type='stores',
                records_count=len(stores_data),
                status='success',
                sync_date=datetime.utcnow(),
                details={
                    'created': self.counters['created'],
                    'updated': self.counters['updated'],
                    'errors': self.counters['errors'],
                    'skipped': self.counters['skipped']
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            logger.info(f"Синхронизация складов завершена. Создано: {self.counters['created']}, "
                       f"Обновлено: {self.counters['updated']}, "
                       f"Пропущено: {self.counters['skipped']}, "
                       f"Ошибок: {self.counters['errors']}")
            return True
            
        except Exception as e:
            self.session.rollback()
            
            try:
                # Записываем ошибку в лог
                sync_log = SyncLog(
                    entity_type='stores',
                    records_count=0,
                    status='error',
                    error_message=str(e),
                    sync_date=datetime.utcnow()
                )
                self.session.add(sync_log)
                self.session.commit()
            except Exception as log_error:
                logger.error(f"Не удалось записать ошибку в лог: {log_error}")
            
            logger.error(f"Ошибка синхронизации складов: {e}")
            return False
    
    def _sync_single_store(self, store_data):
        """Синхронизация одного склада"""
        try:
            store_id = store_data.get('id')
            store_type_str = store_data.get('type', 'STORE')
            parent_id = store_data.get('parentId')
            
            # Проверяем, существует ли родительский склад
            if parent_id and not self.session.query(Store).filter(Store.id == parent_id).first():
                logger.warning(f"Родительский склад {parent_id} еще не существует, сбрасываем связь")
                parent_id = None
            
            # Определяем enum-тип склада
            try:
                store_type = StoreType[store_type_str]
            except (KeyError, ValueError):
                logger.warning(f"Неизвестный тип склада: {store_type_str}, используем тип STORE")
                store_type = StoreType.STORE
            
            # Создаем экземпляр склада
            store = Store(
                id=store_id,
                parent_id=parent_id,
                code=store_data.get('code') or None,
                name=store_data.get('name', ''),
                type=store_type,
                synced_at=datetime.utcnow()
            )
            
            self.session.add(store)
            self.counters['created'] += 1
            
            # Коммитим транзакцию
            self.session.commit()
            return True
                
        except Exception as e:
            logger.error(f"Ошибка при синхронизации склада {store_data.get('id')}: {e}")
            self.counters['errors'] += 1
            self.session.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    synchronizer = StoreSynchronizer()
    synchronizer.sync_stores()