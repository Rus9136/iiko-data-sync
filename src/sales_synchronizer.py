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
    
    def sync_sales(self, start_date=None, end_date=None):
        """
        Синхронизация продаж из API IIKO
        
        :param start_date: Начальная дата для получения продаж
        :param end_date: Конечная дата для получения продаж
        """
        logger.info(f"Starting sales synchronization from {start_date} to {end_date}")
        
        try:
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
            
            # Обработка каждой продажи
            for sale_data in sales_data:
                try:
                    self._sync_single_sale(sale_data)
                except Exception as e:
                    logger.error(f"Error syncing sale: {str(e)}")
                    logger.error(traceback.format_exc())
                    self.stats["errors"] += 1
            
            # Фиксация транзакции
            self.session.commit()
            
            # Запись в лог информации о синхронизации
            logger.info(f"Sales synchronization finished. Stats: {self.stats}")
            self._log_sync_result("success", total_sales)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during sales synchronization: {str(e)}")
            logger.error(traceback.format_exc())
            self.session.rollback()
            self._log_sync_result("error", 0, error_message=str(e))
            return False
        finally:
            self.session.close()
    
    def _sync_single_sale(self, sale_data):
        """
        Обработка и сохранение данных одной продажи
        
        :param sale_data: Данные продажи из API
        """
        order_num = int(sale_data.get("OrderNum", 0))
        fiscal_cheque_number = sale_data.get("FiscalChequeNumber")
        
        # Проверяем существует ли уже такая продажа
        existing_sale = self.session.query(Sale).filter(
            Sale.order_num == order_num,
            Sale.fiscal_cheque_number == fiscal_cheque_number
        ).first()
        
        if existing_sale:
            logger.debug(f"Sale with order_num={order_num}, fiscal_cheque_number={fiscal_cheque_number} already exists, updating")
            # Обновляем существующую запись
            self._update_sale(existing_sale, sale_data)
            self.stats["updated"] += 1
        else:
            logger.debug(f"Creating new sale with order_num={order_num}, fiscal_cheque_number={fiscal_cheque_number}")
            # Создаем новую запись
            self._create_sale(sale_data)
            self.stats["created"] += 1
    
    def _create_sale(self, sale_data):
        """
        Создание новой записи продажи
        
        :param sale_data: Данные продажи из API
        """
        try:
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
            sale.synced_at = datetime.utcnow()
            
            logger.debug(f"Updated sale: {sale.id}")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating sale: {str(e)}")
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