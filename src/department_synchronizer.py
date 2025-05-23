import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import uuid

from .models import Department, SyncLog
from .api_client import IikoApiClient

logger = logging.getLogger(__name__)


class DepartmentSynchronizer:
    def __init__(self, api_client: IikoApiClient, connection_string: str):
        self.api_client = api_client
        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def sync_departments(self) -> Dict[str, any]:
        """Синхронизация подразделений из IIKO API"""
        logger.info("Начинаем синхронизацию подразделений...")
        start_time = datetime.now()
        
        try:
            # Получаем данные из API
            departments_data = self.api_client.get_departments()
            logger.info(f"Получено {len(departments_data)} подразделений из API")
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for dept_data in departments_data:
                try:
                    dept_id = uuid.UUID(dept_data['id'])
                    
                    # Проверяем существующее подразделение
                    existing_dept = self.session.query(Department).filter_by(id=dept_id).first()
                    
                    if existing_dept:
                        # Обновляем существующее подразделение
                        existing_dept.parent_id = uuid.UUID(dept_data['parentId']) if dept_data.get('parentId') else None
                        existing_dept.code = dept_data.get('code')
                        existing_dept.name = dept_data['name']
                        existing_dept.type = dept_data.get('type', 'DEPARTMENT')
                        existing_dept.taxpayer_id_number = dept_data.get('taxpayerIdNumber')
                        existing_dept.updated_at = datetime.utcnow()
                        existing_dept.synced_at = datetime.utcnow()
                        updated_count += 1
                        logger.debug(f"Обновлено подразделение: {dept_data['name']}")
                    else:
                        # Создаем новое подразделение
                        new_dept = Department(
                            id=dept_id,
                            parent_id=uuid.UUID(dept_data['parentId']) if dept_data.get('parentId') else None,
                            code=dept_data.get('code'),
                            name=dept_data['name'],
                            type=dept_data.get('type', 'DEPARTMENT'),
                            taxpayer_id_number=dept_data.get('taxpayerIdNumber'),
                            synced_at=datetime.utcnow()
                        )
                        self.session.add(new_dept)
                        created_count += 1
                        logger.debug(f"Создано новое подразделение: {dept_data['name']}")
                    
                    # Фиксируем каждую запись отдельно для избежания проблем с транзакциями
                    self.session.commit()
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке подразделения {dept_data.get('name', 'Unknown')}: {e}")
                    self.session.rollback()
                    skipped_count += 1
            
            # Создаем запись в логе синхронизации
            sync_log = SyncLog(
                entity_type='departments',
                records_count=len(departments_data),
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
                'total': len(departments_data),
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'duration': (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"Синхронизация подразделений завершена: создано {created_count}, обновлено {updated_count}, пропущено {skipped_count}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации подразделений: {e}")
            self.session.rollback()
            
            # Логируем ошибку
            sync_log = SyncLog(
                entity_type='departments',
                records_count=0,
                status='error',
                error_message=str(e)
            )
            self.session.add(sync_log)
            self.session.commit()
            
            raise
        
        finally:
            self.session.close()
    
    def get_department_by_id(self, dept_id: str) -> Optional[Department]:
        """Получение подразделения по ID"""
        try:
            return self.session.query(Department).filter_by(id=uuid.UUID(dept_id)).first()
        except Exception as e:
            logger.error(f"Ошибка при получении подразделения {dept_id}: {e}")
            return None
    
    def get_all_departments(self) -> List[Department]:
        """Получение всех подразделений"""
        try:
            return self.session.query(Department).order_by(Department.name).all()
        except Exception as e:
            logger.error(f"Ошибка при получении списка подразделений: {e}")
            return []
    
    def __del__(self):
        """Закрытие сессии при удалении объекта"""
        if hasattr(self, 'session'):
            self.session.close()