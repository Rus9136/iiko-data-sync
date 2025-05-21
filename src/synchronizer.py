import sys
sys.path.append('/Users/rus/Projects/iiko-data-sync')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json
from datetime import datetime
from src.models import Base, Product, ProductModifier, Category, SyncLog
from src.api_client import IikoApiClient
from config.config import DATABASE_CONFIG
import logging

logger = logging.getLogger(__name__)

class DataSynchronizer:
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
            'errors': 0
        }
    
    def sync_products(self):
        """Синхронизация продуктов из API в БД"""
        try:
            logger.info("Начинаем синхронизацию продуктов...")
            self.counters = {'created': 0, 'updated': 0, 'errors': 0, 'skipped': 0}
            
            # Очищаем таблицу продуктов перед синхронизацией
            try:
                logger.info("Очистка таблицы продуктов перед синхронизацией...")
                product_count = self.session.query(Product).count()
                logger.info(f"Текущее количество продуктов в БД: {product_count}")
                self.session.query(ProductModifier).delete()
                self.session.query(Product).delete()
                self.session.commit()
                logger.info("Таблица продуктов успешно очищена")
            except Exception as e:
                self.session.rollback()
                logger.error(f"Ошибка при очистке таблицы продуктов: {e}")
                raise
            
            # Получаем данные из API
            products_data = self.api_client.get_products()
            logger.info(f"Получено {len(products_data)} продуктов из API")
            
            # Добавляем отладочную информацию о первых и последних продуктах
            if products_data:
                first_products = products_data[:5]
                last_products = products_data[-5:]
                
                logger.info("Первые 5 продуктов из API:")
                for i, p in enumerate(first_products):
                    logger.info(f"  {i+1}. ID: {p.get('id')}, Название: {p.get('name')}, Код: {p.get('code')}")
                    
                logger.info("Последние 5 продуктов из API:")
                for i, p in enumerate(last_products):
                    logger.info(f"  {i+1}. ID: {p.get('id')}, Название: {p.get('name')}, Код: {p.get('code')}")
            else:
                logger.warning("Получен пустой список продуктов из API!")
            
            # Получаем список уже имеющихся id продуктов в БД для оптимизации
            existing_product_ids = set()
            try:
                for row in self.session.query(Product.id).all():
                    existing_product_ids.add(str(row[0]))
                logger.info(f"В базе данных уже есть {len(existing_product_ids)} продуктов")
            except Exception as e:
                logger.error(f"Ошибка при получении существующих ID продуктов: {e}")
                existing_product_ids = set()
            
            # Сначала синхронизируем категории
            try:
                self._extract_and_sync_categories(products_data)
                self.session.commit()
                logger.info("Категории успешно синхронизированы")
            except Exception as e:
                self.session.rollback()
                logger.error(f"Ошибка синхронизации категорий: {e}")
                raise
            
            # Процесс обработки каждого продукта из API
            processed_count = 0
            batch_size = 500
            current_batch = []
            
            for product_data in products_data:
                current_batch.append(product_data)
                processed_count += 1
                
                # Обрабатываем пакетами для оптимизации
                if len(current_batch) >= batch_size:
                    self._process_products_batch(current_batch, existing_product_ids)
                    logger.info(f"Обработано {processed_count} продуктов из {len(products_data)}")
                    current_batch = []
            
            # Обрабатываем оставшиеся продукты
            if current_batch:
                self._process_products_batch(current_batch, existing_product_ids)
                logger.info(f"Обработано {processed_count} продуктов из {len(products_data)}")
            
            # Записываем в лог
            sync_log = SyncLog(
                entity_type='products',
                records_count=len(products_data),
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
            
            logger.info(f"Синхронизация завершена. Создано: {self.counters['created']}, "
                       f"Обновлено: {self.counters['updated']}, "
                       f"Пропущено: {self.counters['skipped']}, "
                       f"Ошибок: {self.counters['errors']}")
            return True
            
        except Exception as e:
            self.session.rollback()
            
            try:
                # Записываем ошибку в лог
                sync_log = SyncLog(
                    entity_type='products',
                    records_count=0,
                    status='error',
                    error_message=str(e),
                    sync_date=datetime.utcnow()
                )
                self.session.add(sync_log)
                self.session.commit()
            except Exception as log_error:
                logger.error(f"Не удалось записать ошибку в лог: {log_error}")
            
            logger.error(f"Ошибка синхронизации: {e}")
            return False
            
    def _process_products_batch(self, products_batch, existing_product_ids):
        """Обработка пакета продуктов с применением оптимизаций и устойчивой обработкой ошибок"""
        # Создаем меньшие подпакеты для более устойчивой обработки
        sub_batch_size = 50
        total_processed = 0
        success_count = 0
        
        # Разбиваем большой пакет на более мелкие для устойчивости
        for i in range(0, len(products_batch), sub_batch_size):
            sub_batch = products_batch[i:i+sub_batch_size]
            success = self._process_small_products_batch(sub_batch, existing_product_ids)
            
            total_processed += len(sub_batch)
            if success:
                success_count += len(sub_batch)
                
        return (success_count > 0)
    
    def _process_small_products_batch(self, products_batch, existing_product_ids):
        """Обработка небольшого пакета продуктов с применением оптимизаций"""
        # Этап 1: Создаем записи с базовой информацией (без родительских ссылок)
        products_to_create = []
        products_to_update = []
        
        for product_data in products_batch:
            try:
                product_id = product_data.get('id')
                # Проверяем существование по ID
                if product_id in existing_product_ids:
                    # Продукт уже существует, добавляем в список на обновление
                    products_to_update.append(product_data)
                else:
                    # Создаем новый продукт
                    products_to_create.append(product_data)
            except Exception as e:
                self.counters['errors'] += 1
                logger.error(f"Ошибка при предварительной обработке продукта {product_data.get('id')}: {e}")
        
        # Создаем новые продукты
        for product_data in products_to_create:
            try:
                product_id = product_data.get('id')
                # Создаем новый продукт с базовой информацией
                success = self._create_product_basic(product_data)
                # Если успешно создан, добавляем ID в множество существующих для будущих проверок
                if success:
                    existing_product_ids.add(product_id)
            except Exception as e:
                self.counters['errors'] += 1
                logger.error(f"Ошибка создания продукта {product_data.get('id')}: {e}")
                self.session.rollback()
                
        # Обновляем существующие продукты
        for product_data in products_to_update:
            try:
                product_id = product_data.get('id')
                # Обновляем существующий продукт
                self._update_product_basic_by_id(product_id, product_data)
            except Exception as e:
                self.counters['errors'] += 1
                logger.error(f"Ошибка обновления продукта {product_data.get('id')}: {e}")
                self.session.rollback()
        
        try:
            # Коммитим первый этап
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка коммита базовых записей: {e}")
            return False
        
        # Этап 2: Обновляем связи и модификаторы
        for product_data in products_batch:
            product_id = product_data.get('id')
            try:
                # Обновляем связи
                self._update_product_relations(product_data)
                
                # Обновляем модификаторы, если они есть
                if product_data.get('modifiers'):
                    self._sync_modifiers(product_id, product_data.get('modifiers', []))
            except Exception as e:
                self.counters['errors'] += 1
                logger.error(f"Ошибка обновления связей/модификаторов продукта {product_id}: {e}")
                self.session.rollback()
        
        try:
            # Коммитим второй этап
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка коммита связей и модификаторов: {e}")
            return False
    
    def _extract_and_sync_categories(self, products_data):
        """Извлекает и синхронизирует категории из продуктов"""
        category_ids = set()
        
        for product in products_data:
            if product.get('taxCategory'):
                category_ids.add((product['taxCategory'], 'tax'))
            if product.get('category'):
                category_ids.add((product['category'], 'product'))
            if product.get('accountingCategory'):
                category_ids.add((product['accountingCategory'], 'accounting'))
        
        for category_id, category_type in category_ids:
            if not self.session.query(Category).filter_by(id=category_id).first():
                category = Category(
                    id=category_id,
                    category_type=category_type,
                    name=f"{category_type}_category_{category_id[:8]}"  # Временное имя
                )
                self.session.add(category)
        
        self.session.commit()
    
    def _sync_single_product(self, product_data):
        """Синхронизация одного продукта (метод для обратной совместимости)"""
        try:
            product_id = product_data.get('id')
            
            # Получаем код и проверяем, что он не пустой
            code = product_data.get('code')
            if code == '':
                code = None  # Convert empty string to NULL for database
                
            # Проверяем, существует ли продукт
            existing_product = self.session.query(Product).filter_by(id=product_id).first()
            
            if existing_product:
                # Обновляем существующий продукт
                existing_product.deleted = product_data.get('deleted', False)
                existing_product.name = product_data.get('name', existing_product.name)
                existing_product.description = product_data.get('description')
                existing_product.num = product_data.get('num')
                existing_product.code = code
                existing_product.parent_id = product_data.get('parent')
                existing_product.tax_category_id = product_data.get('taxCategory')
                existing_product.category_id = product_data.get('category')
                existing_product.accounting_category_id = product_data.get('accountingCategory')
                existing_product.updated_at = datetime.utcnow()
                existing_product.synced_at = datetime.utcnow()
                self.counters['updated'] += 1
            else:
                # Создаем новый продукт
                product = Product(
                    id=product_id,
                    deleted=product_data.get('deleted', False),
                    name=product_data.get('name', ''),
                    description=product_data.get('description'),
                    num=product_data.get('num'),
                    code=code,
                    parent_id=product_data.get('parent'),
                    tax_category_id=product_data.get('taxCategory'),
                    category_id=product_data.get('category'),
                    accounting_category_id=product_data.get('accountingCategory'),
                    synced_at=datetime.utcnow()
                )
                self.session.add(product)
                self.counters['created'] += 1
            
            # Синхронизируем модификаторы, если они есть
            if product_data.get('modifiers'):
                self._sync_modifiers(product_id, product_data.get('modifiers', []))
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации продукта {product_data.get('id')}: {e}")
            self.counters['errors'] += 1
            self.session.rollback()
            raise
    
    def _update_product_basic_by_id(self, product_id, product_data):
        """Обновление базовой информации о продукте по ID (без родительских ссылок)"""
        try:
            # Получаем продукт по ID
            existing_product = self.session.query(Product).filter_by(id=product_id).first()
            
            if not existing_product:
                logger.warning(f"Продукт с ID {product_id} не найден в базе для обновления")
                self.counters['skipped'] += 1
                return False
                
            # Получаем код и проверяем, что он не пустой
            code = product_data.get('code')
            if code == '':
                code = None  # Convert empty string to NULL for database
            
            # Обновляем базовую информацию
            existing_product.deleted = product_data.get('deleted', False)
            existing_product.name = product_data.get('name', existing_product.name)
            existing_product.description = product_data.get('description')
            existing_product.num = product_data.get('num')
            existing_product.code = code
            existing_product.updated_at = datetime.utcnow()
            existing_product.synced_at = datetime.utcnow()
            
            self.counters['updated'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении продукта {product_id}: {e}")
            self.session.rollback()
            raise
        
    def _create_product_basic(self, product_data):
        """Создание базовой информации о продукте (без родительских ссылок)"""
        try:
            product_id = product_data.get('id')
            
            # Получаем код и проверяем, что он не пустой
            code = product_data.get('code')
            if code == '':
                code = None  # Convert empty string to NULL for database
            
            # Проверяем, существует ли продукт с таким кодом (если код не пустой)
            if code:
                existing_product_by_code = self.session.query(Product).filter_by(code=code).first()
                if existing_product_by_code:
                    logger.warning(f"Продукт с кодом {code} уже существует (id: {existing_product_by_code.id}). Пропускаем создание нового продукта {product_id}.")
                    self.counters['skipped'] += 1
                    return False
            
            # Создаем новый продукт с базовой информацией, без родительских ссылок
            product = Product(
                id=product_id,
                deleted=product_data.get('deleted', False),
                name=product_data.get('name', ''),
                description=product_data.get('description'),
                num=product_data.get('num'),
                code=code,
                synced_at=datetime.utcnow()
            )
            self.session.add(product)
            self.counters['created'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при создании продукта {product_data.get('id')}: {e}")
            self.session.rollback()
            raise
    
    def _update_product_relations(self, product_data):
        """Обновление связей продукта (родительские и категории)"""
        try:
            product_id = product_data.get('id')
            product = self.session.query(Product).filter_by(id=product_id).first()
            
            if not product:
                logger.warning(f"Продукт {product_id} не найден для обновления связей")
                return
            
            # Проверяем существование родительского продукта
            parent_id = product_data.get('parent')
            if parent_id:
                parent_exists = self.session.query(Product).filter_by(id=parent_id).first() is not None
                if not parent_exists:
                    logger.warning(f"Родительский продукт {parent_id} для продукта {product_id} не найден. Пропускаем установку связи.")
                    parent_id = None  # Обнуляем parent_id, если родитель не существует
            
            # Обновляем родительские и категорийные ссылки
            product.parent_id = parent_id
            product.tax_category_id = product_data.get('taxCategory')
            product.category_id = product_data.get('category')
            product.accounting_category_id = product_data.get('accountingCategory')
            product.updated_at = datetime.utcnow()
            product.synced_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении связей продукта {product_data.get('id')}: {e}")
            self.session.rollback()
            raise
        
    def _create_product(self, product_data):
        """Устаревший метод создания продукта (для обратной совместимости)"""
        self._create_product_basic(product_data)
        self._update_product_relations(product_data)
    
    def _update_product(self, product, product_data):
        """Устаревший метод обновления продукта (для обратной совместимости)"""
        product.deleted = product_data.get('deleted', False)
        product.name = product_data.get('name', product.name)
        product.description = product_data.get('description')
        product.num = product_data.get('num')
        product.code = product_data.get('code')
        product.parent_id = product_data.get('parent')
        product.tax_category_id = product_data.get('taxCategory')
        product.category_id = product_data.get('category')
        product.accounting_category_id = product_data.get('accountingCategory')
        product.updated_at = datetime.utcnow()
        product.synced_at = datetime.utcnow()
    
    def _sync_modifiers(self, product_id, modifiers_data):
        """Синхронизация модификаторов продукта"""
        try:
            # Удаляем старые связи
            self.session.query(ProductModifier).filter_by(product_id=product_id).delete()
            
            # Добавляем новые
            for position, modifier_data in enumerate(modifiers_data):
                # Проверяем формат данных модификатора
                if isinstance(modifier_data, dict) and 'modifier' in modifier_data:
                    # Формат: {'modifier': 'id', ...другие данные...}
                    modifier_id = modifier_data['modifier']
                elif isinstance(modifier_data, dict):
                    # Неизвестный формат словаря
                    logger.warning(f"Пропуск модификатора в неизвестном формате: {modifier_data}")
                    continue
                else:
                    # Простой формат: строка с ID модификатора
                    modifier_id = modifier_data
                
                # Создаем связь
                product_modifier = ProductModifier(
                    product_id=product_id,
                    modifier_id=modifier_id,
                    position=position
                )
                self.session.add(product_modifier)
                
        except Exception as e:
            logger.error(f"Ошибка при синхронизации модификаторов для продукта {product_id}: {e}")
            self.session.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    synchronizer = DataSynchronizer()
    synchronizer.sync_products()
