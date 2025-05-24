import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import uuid

from .models import Supplier, SyncLog
from .api_client import IikoApiClient

logger = logging.getLogger(__name__)


class SupplierSynchronizer:
    def __init__(self, api_client: IikoApiClient, connection_string: str):
        self.api_client = api_client
        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def sync_suppliers(self) -> Dict[str, any]:
        """Синхронизация поставщиков из IIKO API"""
        logger.info("Начинаем синхронизацию поставщиков...")
        start_time = datetime.now()
        
        try:
            # Получаем данные из API
            suppliers_data = self.api_client.get_suppliers()
            logger.info(f"Получено {len(suppliers_data)} поставщиков из API")
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for supplier_data in suppliers_data:
                try:
                    supplier_id = uuid.UUID(supplier_data['id'])
                    
                    # Проверяем существующего поставщика
                    existing_supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
                    
                    if existing_supplier:
                        # Обновляем существующего поставщика
                        existing_supplier.code = supplier_data.get('code')
                        existing_supplier.name = supplier_data['name']
                        existing_supplier.login = supplier_data.get('login')
                        existing_supplier.card_number = supplier_data.get('cardNumber')
                        existing_supplier.taxpayer_id_number = supplier_data.get('taxpayerIdNumber')
                        existing_supplier.snils = supplier_data.get('snils')
                        existing_supplier.deleted = supplier_data.get('deleted', False)
                        existing_supplier.is_supplier = supplier_data.get('supplier', True)
                        existing_supplier.is_employee = supplier_data.get('employee', False)
                        existing_supplier.is_client = supplier_data.get('client', False)
                        existing_supplier.represents_store = supplier_data.get('representsStore', False)
                        existing_supplier.updated_at = datetime.utcnow()
                        existing_supplier.synced_at = datetime.utcnow()
                        updated_count += 1
                        logger.debug(f"Обновлен поставщик: {supplier_data['name']}")
                    else:
                        # Создаем нового поставщика
                        new_supplier = Supplier(
                            id=supplier_id,
                            code=supplier_data.get('code'),
                            name=supplier_data['name'],
                            login=supplier_data.get('login'),
                            card_number=supplier_data.get('cardNumber'),
                            taxpayer_id_number=supplier_data.get('taxpayerIdNumber'),
                            snils=supplier_data.get('snils'),
                            deleted=supplier_data.get('deleted', False),
                            is_supplier=supplier_data.get('supplier', True),
                            is_employee=supplier_data.get('employee', False),
                            is_client=supplier_data.get('client', False),
                            represents_store=supplier_data.get('representsStore', False),
                            synced_at=datetime.utcnow()
                        )
                        self.session.add(new_supplier)
                        created_count += 1
                        logger.debug(f"Создан новый поставщик: {supplier_data['name']}")
                    
                    # Фиксируем каждую запись отдельно для избежания проблем с транзакциями
                    self.session.commit()
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке поставщика {supplier_data.get('name', 'Unknown')}: {e}")
                    self.session.rollback()
                    skipped_count += 1
            
            # Создаем запись в логе синхронизации
            sync_log = SyncLog(
                entity_type='suppliers',
                records_count=len(suppliers_data),
                status='success',
                details={
                    'created': created_count,
                    'updated': updated_count,
                    'skipped': skipped_count,
                    'duration_seconds': (datetime.now() - start_time).total_seconds()
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            result = {
                'status': 'success',
                'total': len(suppliers_data),
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'duration': (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"Синхронизация поставщиков завершена: создано {created_count}, обновлено {updated_count}, пропущено {skipped_count}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации поставщиков: {e}")
            self.session.rollback()
            
            # Логируем ошибку
            sync_log = SyncLog(
                entity_type='suppliers',
                records_count=0,
                status='error',
                error_message=str(e)
            )
            self.session.add(sync_log)
            self.session.commit()
            
            raise
        
        finally:
            self.session.close()
    
    def get_supplier_by_id(self, supplier_id: str) -> Optional[Supplier]:
        """Получение поставщика по ID"""
        try:
            return self.session.query(Supplier).filter_by(id=uuid.UUID(supplier_id)).first()
        except Exception as e:
            logger.error(f"Ошибка при получении поставщика {supplier_id}: {e}")
            return None
    
    def get_all_suppliers(self, include_deleted: bool = False) -> List[Supplier]:
        """Получение всех поставщиков"""
        try:
            query = self.session.query(Supplier)
            if not include_deleted:
                query = query.filter_by(deleted=False)
            return query.order_by(Supplier.name).all()
        except Exception as e:
            logger.error(f"Ошибка при получении списка поставщиков: {e}")
            return []
    
    def __del__(self):
        """Закрытие сессии при удалении объекта"""
        if hasattr(self, 'session'):
            self.session.close()