import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import traceback

from src.models import Base, Sale, SyncLog, Store
from src.api_client import IikoApiClient
from config.config import DATABASE_CONFIG

# Настройка логирования
log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "sync_sales.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logger = logging.getLogger("sales_synchronizer")
logger.setLevel(logging.INFO)

# Добавляем обработчик для записи в файл
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Добавляем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

class SalesSynchronizer:
    def __init__(self):
        """
        Инициализация синхронизатора продаж
        """
        # Подключение к базе данных
        db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
        # Создание API клиента
        self.api_client = IikoApiClient()
        
        # Статистика
        self.stats = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0
        }
        
        logger.info("Sales synchronizer initialized")
    
    def sync_sales(self, start_date=None, end_date=None, clear_existing=False):
        """
        Синхронизация продаж из API IIKO
        
        :param start_date: Начальная дата для получения продаж
        :param end_date: Конечная дата для получения продаж
        :param clear_existing: Флаг, указывающий нужно ли удалить существующие данные за указанный период
        """
        # Преобразуем формат даты если пришел datetime-local
        if start_date and 'T' in str(start_date):
            start_date = start_date.split('T')[0]
        if end_date and 'T' in str(end_date):
            end_date = end_date.split('T')[0]
            
        logger.info(f"Starting sales synchronization from {start_date} to {end_date} (clear_existing={clear_existing})")
        
        try:
            # Если указан флаг clear_existing, удаляем существующие данные за указанный период
            if clear_existing and start_date and end_date:
                logger.info(f"Clearing existing sales data for period from {start_date} to {end_date}")
                self._clear_existing_sales(start_date, end_date)
                self.stats["deleted"] = self.stats.get("deleted", 0) + 1
            
            # Получение данных о продажах из API
            sales_data = self.api_client.get_sales(start_date, end_date)
            
            if not sales_data:
                logger.warning("No sales data received from API")
                self._log_sync_result("No data received", 0)
                return False
            
            total_sales = len(sales_data)
            logger.info(f"Received {total_sales} sales from API")
            
            # Логирование первых и последних 5 продаж для отладки
            if total_sales > 0:
                first_sales = sales_data[:min(5, total_sales)]
                logger.debug(f"First 5 sales: {json.dumps(first_sales, indent=2)}")
                
                if total_sales > 5:
                    last_sales = sales_data[-5:]
                    logger.debug(f"Last 5 sales: {json.dumps(last_sales, indent=2)}")
            
            # Обработка каждой продажи с батчами для коммитов
            batch_size = 100  # Коммитим каждые 100 записей
            batch_count = 0
            
            for i, sale_data in enumerate(sales_data):
                try:
                    self._sync_single_sale(sale_data)
                    batch_count += 1
                    
                    # Коммитим батч каждые 100 записей
                    if batch_count >= batch_size:
                        try:
                            self.session.commit()
                            batch_count = 0
                            if i % 1000 == 0:  # Логируем прогресс каждые 1000 записей
                                logger.info(f"Processed {i+1}/{len(sales_data)} sales...")
                        except Exception as commit_error:
                            logger.error(f"Error committing batch: {commit_error}")
                            self.session.rollback()
                            self.stats["errors"] += batch_count
                            batch_count = 0
                            
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error syncing sale: {error_msg}")
                    # Для дублирующихся ключей или других constraint нарушений
                    if any(keyword in error_msg.lower() for keyword in ["duplicate key", "unique constraint", "violates"]):
                        logger.debug(f"Constraint violation for sale: order_num={sale_data.get('OrderNum')}, fiscal_cheque_number={sale_data.get('FiscalChequeNumber')}, dish_code={sale_data.get('DishCode')}")
                        self.session.rollback()
                        batch_count = 0
                    else:
                        logger.error(traceback.format_exc())
                        self.session.rollback()
                        batch_count = 0
                    self.stats["errors"] += 1
            
            # Финальный коммит для оставшихся записей
            if batch_count > 0:
                try:
                    self.session.commit()
                except Exception as commit_error:
                    logger.error(f"Error in final commit: {commit_error}")
                    self.session.rollback()
            
            # Запись в лог информации о синхронизации
            logger.info(f"Sales synchronization finished. Stats: {self.stats}")
            self._log_sync_result("success", total_sales)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during sales synchronization: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                self.session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
            self._log_sync_result("error", 0, error_message=str(e))
            return False
        finally:
            try:
                self.session.close()
            except Exception as close_error:
                logger.error(f"Error closing session: {close_error}")
    
    def _sync_single_sale(self, sale_data):
        """
        Обработка и сохранение данных одной продажи с использованием upsert
        
        :param sale_data: Данные продажи из API
        """
        from sqlalchemy.dialects.postgresql import insert
        
        # Проверяем, не является ли чек отмененным
        is_storned = sale_data.get("Storned", "").upper() == "TRUE" or sale_data.get("Storned") is True
        if is_storned:
            logger.debug(f"Skipping storned sale: order_num={sale_data.get('OrderNum')}")
            self.stats["skipped"] += 1
            return
        
        order_num = int(sale_data.get("OrderNum", 0))
        fiscal_cheque_number = sale_data.get("FiscalChequeNumber")
        dish_code = sale_data.get("DishCode")
        cash_register_number = sale_data.get("CashRegisterName.Number")
        
        try:
            with self.session.no_autoflush:
                # Подготавливаем данные для upsert
                sale_dict = self._prepare_sale_data(sale_data)
                
                # Используем PostgreSQL UPSERT (INSERT ... ON CONFLICT ... DO UPDATE)
                stmt = insert(Sale).values(**sale_dict)
                
                # При конфликте обновляем все поля кроме уникального ключа и id
                update_dict = {key: stmt.excluded[key] for key in sale_dict.keys() 
                              if key not in ['id', 'order_num', 'fiscal_cheque_number', 'dish_code', 'cash_register_number', 'created_at']}
                update_dict['updated_at'] = stmt.excluded.updated_at
                update_dict['synced_at'] = stmt.excluded.synced_at
                
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=['order_num', 'fiscal_cheque_number', 'dish_code', 'cash_register_number'],
                    set_=update_dict
                )
                
                result = self.session.execute(upsert_stmt)
                
                # Определяем, была ли запись создана или обновлена
                if result.rowcount > 0:
                    # Проверяем, была ли запись создана (INSERT) или обновлена (UPDATE)
                    # Для PostgreSQL это сложно определить напрямую, поэтому считаем как created
                    self.stats["created"] += 1
                    logger.debug(f"Upserted sale: order_num={order_num}, fiscal_cheque_number={fiscal_cheque_number}")
            
        except Exception as e:
            logger.error(f"Error in upsert for sale order_num={order_num}: {e}")
            logger.error(f"Sale data: order_num={order_num}, fiscal_cheque_number={fiscal_cheque_number}, dish_code={dish_code}, cash_register_number={cash_register_number}")
            self.stats["errors"] = self.stats.get("errors", 0) + 1
            raise e
    
    def _prepare_sale_data(self, sale_data):
        """
        Подготавливает данные продажи в формате словаря для upsert
        
        :param sale_data: Данные продажи из API
        :return: Словарь с данными для вставки/обновления
        """
        # Получаем связанный склад по имени, если есть
        store_name = sale_data.get("Store.Name")
        store_id = None
        
        if store_name:
            store = self.session.query(Store).filter(Store.name == store_name).first()
            if store:
                store_id = store.id
        
        # Обработка полей с датами
        close_time = None
        if sale_data.get("CloseTime"):
            try:
                close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                try:
                    close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    logger.warning(f"Could not parse CloseTime: {sale_data['CloseTime']}")
        
        precheque_time = None
        if sale_data.get("PrechequeTime"):
            try:
                precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                try:
                    precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    logger.warning(f"Could not parse PrechequeTime: {sale_data['PrechequeTime']}")
        
        # Возвращаем словарь с данными (UUID генерируется только при INSERT, исключен для UPDATE)
        return {
            'id': uuid.uuid4(),  # Это будет использоваться только при INSERT
            'order_num': int(sale_data.get("OrderNum", 0)),
            'fiscal_cheque_number': sale_data.get("FiscalChequeNumber"),
            'cash_register_name': sale_data.get("CashRegisterName"),
            'cash_register_serial_number': sale_data.get("CashRegisterName.CashRegisterSerialNumber"),
            'cash_register_number': int(sale_data.get("CashRegisterName.Number", 0)) if sale_data.get("CashRegisterName.Number") else None,
            'close_time': close_time,
            'precheque_time': precheque_time,
            'deleted_with_writeoff': sale_data.get("DeletedWithWriteoff", "NOT_DELETED"),
            'department': sale_data.get("Department"),
            'department_id': uuid.UUID(sale_data["DepartmentId"]) if sale_data.get("DepartmentId") else None,
            # Исправлены типы данных - используем Integer как в модели
            'dish_amount': int(sale_data.get("DishAmountInt", 0)) if sale_data.get("DishAmountInt") is not None else None,
            'dish_code': sale_data.get("DishCode"),
            'dish_discount_sum': int(sale_data.get("DishDiscountSumInt", 0)) if sale_data.get("DishDiscountSumInt") is not None else None,
            'dish_measure_unit': sale_data.get("DishMeasureUnit"),
            'dish_name': sale_data.get("DishName"),
            'dish_return_sum': int(sale_data.get("DishReturnSumInt", 0)) if sale_data.get("DishReturnSumInt") is not None else None,
            'dish_sum': int(sale_data.get("DishSumInt", 0)) if sale_data.get("DishSumInt") is not None else None,
            'increase_sum': int(sale_data.get("IncreaseSumInt", 0)) if sale_data.get("IncreaseSumInt") is not None else None,
            'order_increase_type': sale_data.get("OrderIncreaseType", ""),
            'order_items': int(sale_data.get("OrderItems", 0)) if sale_data.get("OrderItems") else None,
            'order_type': sale_data.get("OrderType"),
            'pay_types': sale_data.get("PayTypes"),
            'store_name': store_name,
            'store_id': store_id,
            'storned': sale_data.get("Storned", "").upper() == "TRUE" or sale_data.get("Storned") is True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'synced_at': datetime.utcnow()
        }
    
    def _create_sale(self, sale_data):
        """
        Создание новой записи продажи
        
        :param sale_data: Данные продажи из API
        """
        try:
            # Получаем связанный склад по имени, если есть
            store_name = sale_data.get("Store.Name")
            store_id = None
            
            logger.debug(f"Creating sale - Searching for store with name: {store_name}")
            logger.debug(f"Sale data keys: {sale_data.keys()}")
            
            if store_name:
                store = self.session.query(Store).filter(Store.name == store_name).first()
                if store:
                    store_id = store.id
                    logger.debug(f"Found store with id: {store_id}")
                else:
                    logger.warning(f"Store with name '{store_name}' not found in database")
            
            # Обработка полей с датами
            close_time = None
            if sale_data.get("CloseTime"):
                try:
                    close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    try:
                        close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        logger.warning(f"Could not parse CloseTime: {sale_data['CloseTime']}")
            
            precheque_time = None
            if sale_data.get("PrechequeTime"):
                try:
                    precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    try:
                        precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        logger.warning(f"Could not parse PrechequeTime: {sale_data['PrechequeTime']}")
            
            # Создаем новую запись
            new_sale = Sale(
                id=uuid.uuid4(),
                order_num=int(sale_data.get("OrderNum", 0)),
                fiscal_cheque_number=sale_data.get("FiscalChequeNumber"),
                cash_register_name=sale_data.get("CashRegisterName"),
                cash_register_serial_number=sale_data.get("CashRegisterName.CashRegisterSerialNumber"),
                cash_register_number=int(sale_data.get("CashRegisterName.Number", 0)) if sale_data.get("CashRegisterName.Number") else None,
                close_time=close_time,
                precheque_time=precheque_time,
                deleted_with_writeoff=sale_data.get("DeletedWithWriteoff"),
                department=sale_data.get("Department"),
                department_id=sale_data.get("Department.Id"),
                dish_amount=int(sale_data.get("DishAmountInt", 0)) if sale_data.get("DishAmountInt") else None,
                dish_code=sale_data.get("DishCode"),
                dish_discount_sum=int(sale_data.get("DishDiscountSumInt", 0)) if sale_data.get("DishDiscountSumInt") else None,
                dish_measure_unit=sale_data.get("DishMeasureUnit"),
                dish_name=sale_data.get("DishName"),
                dish_return_sum=int(sale_data.get("DishReturnSum", 0)) if sale_data.get("DishReturnSum") else None,
                dish_sum=int(sale_data.get("DishSumInt", 0)) if sale_data.get("DishSumInt") else None,
                increase_sum=int(sale_data.get("IncreaseSum", 0)) if sale_data.get("IncreaseSum") else None,
                order_increase_type=sale_data.get("OrderIncrease.Type"),
                order_items=int(sale_data.get("OrderItems", 0)) if sale_data.get("OrderItems") else None,
                order_type=sale_data.get("OrderType"),
                pay_types=sale_data.get("PayTypes"),
                store_name=store_name,
                store_id=store_id,
                storned=(sale_data.get("Storned", "").upper() == "TRUE"),
                synced_at=datetime.utcnow()
            )
            
            self.session.add(new_sale)
            logger.debug(f"Created new sale: {new_sale.id}")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating sale: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _update_sale(self, sale, sale_data):
        """
        Обновление существующей записи продажи
        
        :param sale: Существующая запись продажи
        :param sale_data: Новые данные продажи из API
        """
        try:
            # Получаем связанный склад по имени, если есть
            store_name = sale_data.get("Store.Name")
            store_id = None
            
            logger.debug(f"Updating sale - Searching for store with name: {store_name}")
            logger.debug(f"Sale data keys: {sale_data.keys()}")
            
            if store_name:
                store = self.session.query(Store).filter(Store.name == store_name).first()
                if store:
                    store_id = store.id
                    logger.debug(f"Found store with id: {store_id}")
                else:
                    logger.warning(f"Store with name '{store_name}' not found in database")
            
            # Обработка полей с датами
            close_time = None
            if sale_data.get("CloseTime"):
                try:
                    close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    try:
                        close_time = datetime.strptime(sale_data["CloseTime"], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        logger.warning(f"Could not parse CloseTime: {sale_data['CloseTime']}")
            
            precheque_time = None
            if sale_data.get("PrechequeTime"):
                try:
                    precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    try:
                        precheque_time = datetime.strptime(sale_data["PrechequeTime"], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        logger.warning(f"Could not parse PrechequeTime: {sale_data['PrechequeTime']}")
            
            # Обновляем поля
            sale.cash_register_name = sale_data.get("CashRegisterName")
            sale.cash_register_serial_number = sale_data.get("CashRegisterName.CashRegisterSerialNumber")
            sale.cash_register_number = int(sale_data.get("CashRegisterName.Number", 0)) if sale_data.get("CashRegisterName.Number") else None
            sale.close_time = close_time
            sale.precheque_time = precheque_time
            sale.deleted_with_writeoff = sale_data.get("DeletedWithWriteoff")
            sale.department = sale_data.get("Department")
            sale.department_id = sale_data.get("Department.Id")
            sale.dish_amount = int(sale_data.get("DishAmountInt", 0)) if sale_data.get("DishAmountInt") else None
            sale.dish_code = sale_data.get("DishCode")
            sale.dish_discount_sum = int(sale_data.get("DishDiscountSumInt", 0)) if sale_data.get("DishDiscountSumInt") else None
            sale.dish_measure_unit = sale_data.get("DishMeasureUnit")
            sale.dish_name = sale_data.get("DishName")
            sale.dish_return_sum = int(sale_data.get("DishReturnSum", 0)) if sale_data.get("DishReturnSum") else None
            sale.dish_sum = int(sale_data.get("DishSumInt", 0)) if sale_data.get("DishSumInt") else None
            sale.increase_sum = int(sale_data.get("IncreaseSum", 0)) if sale_data.get("IncreaseSum") else None
            sale.order_increase_type = sale_data.get("OrderIncrease.Type")
            sale.order_items = int(sale_data.get("OrderItems", 0)) if sale_data.get("OrderItems") else None
            sale.order_type = sale_data.get("OrderType")
            sale.pay_types = sale_data.get("PayTypes")
            sale.store_name = store_name
            sale.store_id = store_id
            sale.storned = (sale_data.get("Storned", "").upper() == "TRUE")
            sale.synced_at = datetime.utcnow()
            
            logger.debug(f"Updated sale: {sale.id}")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating sale: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _clear_existing_sales(self, start_date, end_date):
        """
        Удаление существующих данных о продажах за указанный период
        
        :param start_date: Начальная дата в формате YYYY-MM-DD
        :param end_date: Конечная дата в формате YYYY-MM-DD
        """
        from sqlalchemy import and_
        from datetime import datetime
        
        try:
            # Преобразуем строки в объекты datetime
            try:
                from_date = datetime.strptime(start_date, '%Y-%m-%d')
                to_date = datetime.strptime(end_date, '%Y-%m-%d')
                
                # Добавляем один день к конечной дате, чтобы включить весь день
                from datetime import timedelta
                to_date = to_date + timedelta(days=1)
            except ValueError as e:
                logger.error(f"Invalid date format: {e}")
                return False
            
            # Строим запрос на удаление продаж в указанном диапазоне дат
            query = self.session.query(Sale).filter(
                and_(
                    Sale.close_time >= from_date,
                    Sale.close_time < to_date
                )
            )
            
            # Получаем количество записей для удаления
            count_to_delete = query.count()
            logger.info(f"Found {count_to_delete} sales to delete for period from {start_date} to {end_date}")
            
            # Выполняем удаление
            if count_to_delete > 0:
                query.delete(synchronize_session=False)
                self.session.commit()
                logger.info(f"Deleted {count_to_delete} sales from database")
                return True
            
            return False
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error clearing existing sales: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _log_sync_result(self, status, records_count, error_message=None):
        """
        Запись результата синхронизации в лог
        
        :param status: Статус синхронизации
        :param records_count: Количество обработанных записей
        :param error_message: Сообщение об ошибке (если есть)
        """
        try:
            sync_log = SyncLog(
                entity_type="sales",
                sync_date=datetime.utcnow(),
                records_count=records_count,
                status=status,
                error_message=error_message,
                details=self.stats
            )
            self.session.add(sync_log)
            self.session.commit()
        except Exception as e:
            logger.error(f"Error logging sync result: {str(e)}")
            logger.error(traceback.format_exc())