import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import uuid

from .models import Price, Department, Product, SyncLog
from .api_client import IikoApiClient

logger = logging.getLogger(__name__)


class PriceSynchronizer:
    def __init__(self, api_client: IikoApiClient, connection_string: str):
        self.api_client = api_client
        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def sync_prices(self, department_id: str, date_from: str, date_to: str, price_type: str = 'BASE') -> Dict[str, any]:
        """Синхронизация цен для конкретного подразделения за период"""
        logger.info(f"Начинаем синхронизацию цен для подразделения {department_id} с {date_from} по {date_to}")
        start_time = datetime.now()
        
        try:
            # Проверяем существование подразделения
            department = self.session.query(Department).filter_by(id=department_id).first()
            if not department:
                raise ValueError(f"Подразделение с ID {department_id} не найдено")
            
            # Получаем данные из API
            prices_data = self.api_client.get_prices(department_id, date_from, date_to, price_type)
            logger.info(f"Получено {len(prices_data)} записей о ценах из API")
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Удаляем старые цены для этого подразделения и периода
            self.session.query(Price).filter(
                and_(
                    Price.department_id == uuid.UUID(department_id),
                    Price.price_type == price_type,
                    Price.date_from >= datetime.strptime(date_from, '%Y-%m-%d').date(),
                    Price.date_to <= datetime.strptime(date_to, '%Y-%m-%d').date()
                )
            ).delete()
            
            for price_data in prices_data:
                dept_id = uuid.UUID(price_data['departmentId'])
                product_id = uuid.UUID(price_data['productId'])
                product_size_id = uuid.UUID(price_data['productSizeId']) if price_data.get('productSizeId') else None
                
                # Проверяем существование продукта
                product = self.session.query(Product).filter_by(id=product_id).first()
                if not product:
                    logger.warning(f"Продукт с ID {product_id} не найден, пропускаем")
                    skipped_count += 1
                    continue
                
                # Обрабатываем каждую цену в массиве prices
                for price_info in price_data.get('prices', []):
                    try:
                        # Парсим даты
                        price_date_from = datetime.strptime(price_info['dateFrom'], '%Y-%m-%d').date()
                        price_date_to = datetime.strptime(price_info['dateTo'], '%Y-%m-%d').date()
                        
                        # Создаем новую запись о цене
                        new_price = Price(
                            department_id=dept_id,
                            product_id=product_id,
                            product_size_id=product_size_id,
                            price_type=price_type,
                            date_from=price_date_from,
                            date_to=price_date_to,
                            price=price_info['price'],
                            tax_category_id=uuid.UUID(price_info['taxCategoryId']) if price_info.get('taxCategoryId') else None,
                            tax_category_enabled=price_info.get('taxCategoryEnabled', False),
                            included=price_info.get('included', True),
                            dish_of_day=price_info.get('dishOfDay', False),
                            flyer_program=price_info.get('flyerProgram', False),
                            document_id=uuid.UUID(price_info['documentId']) if price_info.get('documentId') else None,
                            schedule=price_info.get('schedule'),
                            synced_at=datetime.utcnow()
                        )
                        self.session.add(new_price)
                        created_count += 1
                        
                    except Exception as e:
                        logger.error(f"Ошибка при обработке цены для продукта {product_id}: {e}")
                        skipped_count += 1
            
            # Фиксируем изменения
            self.session.commit()
            
            # Создаем запись в логе синхронизации
            sync_log = SyncLog(
                entity_type='prices',
                records_count=created_count,
                status='success',
                details={
                    'department_id': department_id,
                    'department_name': department.name,
                    'date_from': date_from,
                    'date_to': date_to,
                    'price_type': price_type,
                    'created': created_count,
                    'skipped': skipped_count,
                    'duration_seconds': (datetime.now() - start_time).total_seconds()
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            result = {
                'status': 'success',
                'department_id': department_id,
                'department_name': department.name,
                'total': len(prices_data),
                'created': created_count,
                'skipped': skipped_count,
                'duration': (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"Синхронизация цен завершена: создано {created_count}, пропущено {skipped_count}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации цен: {e}")
            self.session.rollback()
            
            # Логируем ошибку
            sync_log = SyncLog(
                entity_type='prices',
                records_count=0,
                status='error',
                error_message=str(e),
                details={
                    'department_id': department_id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'price_type': price_type
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            raise
        
        finally:
            self.session.close()
    
    def get_prices_by_department(self, department_id: Optional[str] = None) -> List[Price]:
        """Получение цен с фильтрацией по подразделению"""
        try:
            query = self.session.query(Price).join(Product).join(Department)
            
            if department_id:
                query = query.filter(Price.department_id == uuid.UUID(department_id))
            
            return query.order_by(Price.department_id, Price.product_id, Price.date_from).all()
        except Exception as e:
            logger.error(f"Ошибка при получении списка цен: {e}")
            return []
    
    def __del__(self):
        """Закрытие сессии при удалении объекта"""
        if hasattr(self, 'session'):
            self.session.close()