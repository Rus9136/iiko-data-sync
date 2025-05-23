import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from sqlalchemy import create_engine, func, desc, or_, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

from src.models import Base, Product, Category, SyncLog, Store, Sale, Account, WriteoffDocument, WriteoffItem
from src.synchronizer import DataSynchronizer
from src.store_synchronizer import StoreSynchronizer
from src.sales_synchronizer import SalesSynchronizer
from config.config import DATABASE_CONFIG
from web.report_controller import get_sales_report

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
CORS(app)  # Включаем CORS для всех маршрутов

# Подключение к базе данных
db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

def is_ajax_request():
    """Проверяет, является ли запрос AJAX"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

@app.route('/')
def index():
    """Главная страница"""
    session = Session()
    try:
        # Получаем статистику по продуктам
        total_products = session.query(func.count(Product.id)).scalar() or 0
        active_products = session.query(func.count(Product.id)).filter(Product.deleted == False).scalar() or 0
        deleted_products = session.query(func.count(Product.id)).filter(Product.deleted == True).scalar() or 0
        
        # Получаем статистику по складам
        total_stores = session.query(func.count(Store.id)).scalar() or 0
        
        # Получаем статистику по продажам
        total_sales = session.query(func.count(Sale.id)).scalar() or 0
        
        # Получаем статистику по счетам
        try:
            total_accounts = session.query(func.count(Account.id)).scalar() or 0
            active_accounts = session.query(func.count(Account.id)).filter(Account.deleted == False).scalar() or 0
        except Exception as e:
            app.logger.warning(f"Ошибка при получении статистики счетов: {e}")
            total_accounts = 0
            active_accounts = 0
        
        # Получаем статистику по документам списания
        try:
            total_writeoffs = session.query(func.count(WriteoffDocument.id)).scalar() or 0
            total_writeoff_items = session.query(func.count(WriteoffItem.id)).scalar() or 0
        except Exception as e:
            app.logger.warning(f"Ошибка при получении статистики списаний: {e}")
            total_writeoffs = 0
            total_writeoff_items = 0
        
        # Последняя синхронизация (берем самую позднюю)
        last_sync_products = session.query(SyncLog).filter(SyncLog.entity_type == 'products').order_by(SyncLog.sync_date.desc()).first()
        last_sync_stores = session.query(SyncLog).filter(SyncLog.entity_type == 'stores').order_by(SyncLog.sync_date.desc()).first()
        last_sync_sales = session.query(SyncLog).filter(SyncLog.entity_type == 'sales').order_by(SyncLog.sync_date.desc()).first()
        last_sync_accounts = session.query(SyncLog).filter(SyncLog.entity_type == 'accounts').order_by(SyncLog.sync_date.desc()).first()
        last_sync_writeoffs = session.query(SyncLog).filter(SyncLog.entity_type == 'writeoffs').order_by(SyncLog.sync_date.desc()).first()
        
        # Находим самую позднюю синхронизацию среди всех типов
        all_syncs = [s for s in [last_sync_products, last_sync_stores, last_sync_sales, last_sync_accounts, last_sync_writeoffs] if s is not None]
        last_sync = max(all_syncs, key=lambda x: x.sync_date) if all_syncs else None
        
        # Получаем последние логи для dashboard
        recent_logs = session.query(SyncLog).order_by(SyncLog.sync_date.desc()).limit(5).all()
        
        # Подготовка статистики для dashboard
        stats = {
            'sales_count': total_sales,
            'products_count': total_products,
            'products_updated': active_products,
            'stores_count': total_stores,
            'writeoffs_count': total_writeoffs
        }
        
        # Форматируем последнюю синхронизацию
        if last_sync:
            last_sync_formatted = last_sync.sync_date.strftime('%d.%m.%Y %H:%M')
        else:
            last_sync_formatted = 'Нет данных'
        
        template = 'index.html'
        return render_template(template, 
                             total_products=total_products,
                             active_products=active_products,
                             deleted_products=deleted_products,
                             total_stores=total_stores,
                             total_sales=total_sales,
                             total_accounts=total_accounts,
                             active_accounts=active_accounts,
                             total_writeoffs=total_writeoffs,
                             total_writeoff_items=total_writeoff_items,
                             last_sync=last_sync,
                             recent_logs=recent_logs,
                             stats=stats,
                             last_sync_formatted=last_sync_formatted,
                             db_size='N/A',
                             last_migration='008_create_writeoff_tables.sql')
    finally:
        session.close()

@app.route('/products')
def products():
    """Список продуктов"""
    session = Session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Фильтры
        search = request.args.get('search', '')
        show_deleted = request.args.get('show_deleted', 'false') == 'true'
        
        # Базовый запрос
        query = session.query(Product)
        
        # Применяем фильтры
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%') | Product.code.ilike(f'%{search}%'))
        
        if not show_deleted:
            query = query.filter(Product.deleted == False)
        
        # Пагинация
        total = query.count()
        products = query.order_by(Product.name).offset((page - 1) * per_page).limit(per_page).all()
        
        # Подготовка данных для отображения
        products_data = []
        for product in products:
            products_data.append({
                'id': str(product.id),
                'name': product.name,
                'code': product.code,
                'num': product.num,
                'deleted': product.deleted,
                'description': product.description,
                'category_id': str(product.category_id) if product.category_id else None,
                'parent_id': str(product.parent_id) if product.parent_id else None,
                'synced_at': product.synced_at.strftime('%Y-%m-%d %H:%M:%S') if product.synced_at else None
            })
        
        template = 'products_content.html' if is_ajax_request() else 'products.html'
        return render_template(template, 
                             products=products_data,
                             page=page,
                             total_pages=(total + per_page - 1) // per_page,
                             total=total,
                             search=search,
                             show_deleted=show_deleted)
    finally:
        session.close()

@app.route('/stores')
def stores():
    """Список складов"""
    session = Session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Фильтры
        search = request.args.get('search', '')
        
        # Базовый запрос
        query = session.query(Store)
        
        # Применяем фильтры
        if search:
            query = query.filter(Store.name.ilike(f'%{search}%') | 
                                (Store.code.isnot(None) & Store.code.ilike(f'%{search}%')))
        
        # Пагинация
        total = query.count()
        stores = query.order_by(Store.name).offset((page - 1) * per_page).limit(per_page).all()
        
        # Подготовка данных для отображения
        stores_data = []
        for store in stores:
            stores_data.append({
                'id': str(store.id),
                'name': store.name,
                'code': store.code,
                'type': store.type.name if hasattr(store.type, 'name') else store.type,
                'parent_id': str(store.parent_id) if store.parent_id else None,
                'synced_at': store.synced_at.strftime('%Y-%m-%d %H:%M:%S') if store.synced_at else None
            })
        
        template = 'stores_content.html' if is_ajax_request() else 'stores.html'
        return render_template(template, 
                             stores=stores_data,
                             page=page,
                             total_pages=(total + per_page - 1) // per_page,
                             total=total,
                             search=search)
    finally:
        session.close()

@app.route('/accounts')
def accounts():
    """Список счетов"""
    session = Session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Фильтры
        search = request.args.get('search', '')
        show_deleted = request.args.get('show_deleted', 'false') == 'true'
        
        # Базовый запрос
        query = session.query(Account)
        
        # Применяем фильтры
        if search:
            query = query.filter(Account.name.ilike(f'%{search}%') | 
                                (Account.code.isnot(None) & Account.code.ilike(f'%{search}%')))
        
        if not show_deleted:
            query = query.filter(Account.deleted == False)
        
        # Пагинация
        total = query.count()
        accounts = query.order_by(Account.name).offset((page - 1) * per_page).limit(per_page).all()
        
        # Подготовка данных для отображения
        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': str(account.id),
                'name': account.name,
                'code': account.code,
                'type': account.type,
                'deleted': account.deleted,
                'system': account.system,
                'custom_transactions_allowed': account.custom_transactions_allowed,
                'parent_id': str(account.account_parent_id) if account.account_parent_id else None,
                'synced_at': account.synced_at.strftime('%Y-%m-%d %H:%M:%S') if account.synced_at else None
            })
        
        return render_template('accounts.html', 
                             accounts=accounts_data,
                             page=page,
                             total_pages=(total + per_page - 1) // per_page,
                             total=total,
                             search=search,
                             show_deleted=show_deleted)
    finally:
        session.close()

@app.route('/sync', methods=['POST'])
def sync():
    """Запуск синхронизации"""
    try:
        # Получаем тип синхронизации из JSON-запроса
        data = request.json
        entity = data.get('entity', 'products')
        
        if entity == 'products':
            synchronizer = DataSynchronizer()
            synchronizer.sync_products()
            message = 'Синхронизация продуктов завершена успешно'
        elif entity == 'stores':
            store_synchronizer = StoreSynchronizer()
            store_synchronizer.sync_stores()
            message = 'Синхронизация складов завершена успешно'
        elif entity == 'sales':
            # Получаем параметры для синхронизации продаж
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            clear_existing = data.get('clear_existing', False)
            
            sales_synchronizer = SalesSynchronizer()
            sales_synchronizer.sync_sales(start_date, end_date, clear_existing)
            message = 'Синхронизация продаж завершена успешно'
            
            return jsonify({
                'status': 'success', 
                'message': message,
                'stats': sales_synchronizer.stats
            })
        elif entity == 'accounts':
            synchronizer = DataSynchronizer()
            synchronizer.sync_accounts()
            message = 'Синхронизация счетов завершена успешно'
        elif entity == 'writeoffs':
            # Получаем параметры для синхронизации списаний
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({'status': 'error', 'message': 'Для синхронизации списаний необходимо указать даты'}), 400
            
            synchronizer = DataSynchronizer()
            synchronizer.sync_writeoff_documents(start_date, end_date)
            message = 'Синхронизация документов списания завершена успешно'
            
            return jsonify({
                'status': 'success', 
                'message': message,
                'stats': synchronizer.counters
            })
        else:
            return jsonify({'status': 'error', 'message': f'Неизвестный тип сущности: {entity}'}), 400
            
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        import traceback
        error_message = str(e)
        app.logger.error(f"Sync error: {error_message}")
        app.logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/product/<product_id>')
def product_detail(product_id):
    """Детали продукта"""
    session = Session()
    try:
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            return "Продукт не найден", 404
        
        # Получаем связанные данные
        parent = None
        if product.parent_id:
            parent = session.query(Product).filter_by(id=product.parent_id).first()
        
        children = session.query(Product).filter_by(parent_id=product_id).all()
        
        category = None
        if product.category_id:
            category = session.query(Category).filter_by(id=product.category_id).first()
        
        template = 'product_detail_content.html' if is_ajax_request() else 'product_detail.html'
        return render_template(template, 
                             product=product,
                             parent=parent,
                             children=children,
                             category=category)
    finally:
        session.close()

@app.route('/store/<store_id>')
def store_detail(store_id):
    """Детали склада"""
    session = Session()
    try:
        store = session.query(Store).filter_by(id=store_id).first()
        if not store:
            return "Склад не найден", 404
        
        # Получаем связанные данные
        parent = None
        if store.parent_id:
            parent = session.query(Store).filter_by(id=store.parent_id).first()
        
        children = session.query(Store).filter_by(parent_id=store_id).all()
        
        template = 'store_detail_content.html' if is_ajax_request() else 'store_detail.html'
        return render_template(template, 
                             store=store,
                             parent=parent,
                             children=children)
    finally:
        session.close()

@app.route('/account/<account_id>')
def account_detail(account_id):
    """Детали счета"""
    session = Session()
    try:
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            return "Счет не найден", 404
        
        # Получаем связанные данные
        parent = None
        if account.account_parent_id:
            parent = session.query(Account).filter_by(id=account.account_parent_id).first()
        
        children = session.query(Account).filter_by(account_parent_id=account_id).all()
        
        return render_template('account_detail.html', 
                             account=account,
                             parent=parent,
                             children=children)
    finally:
        session.close()

@app.route('/logs')
def logs():
    """Просмотр логов синхронизации"""
    session = Session()
    try:
        logs = session.query(SyncLog).order_by(SyncLog.sync_date.desc()).limit(50).all()
        template = 'logs_content.html' if is_ajax_request() else 'logs.html'
        return render_template(template, logs=logs)
    finally:
        session.close()

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Загрузка JSON файла с данными"""
    if request.method == 'GET':
        template = 'upload_content.html' if is_ajax_request() else 'upload.html'
        return render_template(template)
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'Файл не выбран'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Файл не выбран'}), 400
        
        if file and file.filename.endswith('.json'):
            try:
                # Читаем JSON данные
                products_data = json.load(file)
                
                # Используем существующий синхронизатор
                synchronizer = DataSynchronizer()
                
                # Извлекаем и синхронизируем категории
                synchronizer._extract_and_sync_categories(products_data)
                
                # Синхронизируем продукты
                for product_data in products_data:
                    synchronizer._sync_single_product(product_data)
                
                synchronizer.session.commit()
                
                # Записываем в лог
                sync_log = SyncLog(
                    entity_type='products',
                    records_count=len(products_data),
                    status='success',
                    sync_date=datetime.utcnow(),
                    details={'source': 'file_upload'}
                )
                synchronizer.session.add(sync_log)
                synchronizer.session.commit()
                
                return jsonify({'status': 'success', 'message': f'Загружено {len(products_data)} продуктов'})
                    
            except Exception as e:
                import traceback
                app.logger.error(f"Upload error: {str(e)}")
                app.logger.error(traceback.format_exc())
                return jsonify({'status': 'error', 'message': str(e)}), 500
        else:
            return jsonify({'status': 'error', 'message': 'Неверный формат файла. Нужен JSON'}), 400
    
    # GET запрос - отображаем страницу
    template = 'upload_content.html' if is_ajax_request() else 'upload.html'
    return render_template(template)

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route('/sales')
def sales():
    """Список чеков (группировка по заказам)"""
    session = Session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Фильтры
        search = request.args.get('search', '')
        date_from = request.args.get('date_from', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))
        store_id = request.args.get('store_id', '')
        
        # Преобразуем строки даты в объекты datetime
        from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
        to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
        
        # Если указана to_date, добавляем 1 день для включения всего дня
        if to_date:
            to_date = to_date + timedelta(days=1)
        
        # Простой подход - получаем уникальные чеки и считаем суммы в Python
        from sqlalchemy import text
        
        # Строим базовые условия фильтрации
        where_conditions = []
        params = {}
        
        if from_date and to_date:
            where_conditions.append("close_time >= :from_date AND close_time < :to_date")
            params['from_date'] = from_date
            params['to_date'] = to_date
        
        if store_id:
            where_conditions.append("store_id = :store_id")
            params['store_id'] = store_id
            
        sale_type = request.args.get('sale_type', 'all')
        if sale_type == 'normal':
            where_conditions.append("storned = false")
        elif sale_type == 'canceled':
            where_conditions.append("storned = true")
        
        # Поисковые условия
        search_conditions = []
        if search:
            search_conditions.append("(fiscal_cheque_number ILIKE :search OR order_num::text ILIKE :search OR department ILIKE :search)")
            params['search'] = f'%{search}%'
        
        # Собираем WHERE clause
        where_clause = ""
        if where_conditions or search_conditions:
            all_conditions = where_conditions + search_conditions
            where_clause = "WHERE " + " AND ".join(all_conditions)
        
        # SQL запрос для группировки чеков
        sql_query = f"""
        SELECT 
            order_num,
            fiscal_cheque_number,
            MAX(close_time) as close_time,
            MAX(cash_register_number) as cash_register_number,
            MAX(cash_register_name) as cash_register_name,
            MAX(department) as department,
            MAX(store_name) as store_name,
            MAX(pay_types) as pay_types,
            BOOL_OR(storned) as storned,
            MAX(deleted_with_writeoff) as deleted_with_writeoff,
            SUM(dish_sum) as order_sum,
            SUM(dish_discount_sum) as order_discount_sum,
            SUM(dish_return_sum) as order_return_sum,
            COUNT(*) as items_count,
            MIN(id::text)::uuid as first_sale_id
        FROM sales
        {where_clause}
        GROUP BY order_num, fiscal_cheque_number
        ORDER BY MAX(close_time) DESC
        LIMIT :limit OFFSET :offset
        """
        
        # Подсчет общего количества
        count_sql = f"""
        SELECT COUNT(DISTINCT (order_num, fiscal_cheque_number))
        FROM sales
        {where_clause}
        """
        
        # Выполняем запросы
        params['limit'] = per_page
        params['offset'] = (page - 1) * per_page
        
        total_count = session.execute(text(count_sql), params).scalar()
        sales = session.execute(text(sql_query), params).fetchall()
        
        # Статистика
        total_sum = sum(sale.order_sum or 0 for sale in sales)
        discount_sum = sum(sale.order_discount_sum or 0 for sale in sales)
        unique_orders = total_count
        
        # Получение списка складов для фильтра
        stores = session.query(Store).order_by(Store.name).all()
        
        template = 'sales_content.html' if is_ajax_request() else 'sales.html'
        return render_template(template, 
                             sales=sales,
                             page=page,
                             total_pages=(total_count + per_page - 1) // per_page,
                             total_count=total_count,
                             total_sum=total_sum,
                             discount_sum=discount_sum,
                             unique_orders=unique_orders,
                             search=search,
                             date_from=date_from,
                             date_to=date_to,
                             store_id=store_id,
                             sale_type=sale_type,
                             stores=stores)
    finally:
        session.close()

@app.route('/sale/<sale_id>')
def sale_detail(sale_id):
    """Детали чека"""
    session = Session()
    try:
        sale = session.query(Sale).filter_by(id=sale_id).first()
        if not sale:
            return "Продажа не найдена", 404
        
        # Получаем все позиции в том же чеке
        related_sales = session.query(Sale).filter(
            Sale.order_num == sale.order_num,
            Sale.fiscal_cheque_number == sale.fiscal_cheque_number
        ).order_by(Sale.dish_name).all()
        
        # Подсчитываем статистику чека
        total_sum = sum(related.dish_sum or 0 for related in related_sales)
        total_discount = sum(related.dish_discount_sum or 0 for related in related_sales)
        total_return = sum(related.dish_return_sum or 0 for related in related_sales)
        total_increase = sum(related.increase_sum or 0 for related in related_sales)
        order_items_count = len(related_sales)
        
        return render_template('sale_detail.html', 
                             sale=sale,
                             related_sales=related_sales,
                             total_sum=total_sum,
                             total_discount=total_discount,
                             total_return=total_return,
                             total_increase=total_increase,
                             order_items_count=order_items_count)
    finally:
        session.close()

@app.route('/sales/sync', methods=['GET', 'POST'])
def sales_sync():
    """Страница ручной синхронизации продаж"""
    if request.method == 'POST':
        try:
            # Получаем параметры синхронизации
            data = request.json
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            clear_existing = data.get('clear_existing', False)
            
            if not start_date or not end_date:
                return jsonify({
                    'status': 'error', 
                    'error': 'Необходимо указать даты начала и окончания'
                }), 400
            
            # Запуск синхронизатора продаж
            sales_synchronizer = SalesSynchronizer()
            result = sales_synchronizer.sync_sales(start_date, end_date, clear_existing)
            
            return jsonify({
                'status': 'success', 
                'message': 'Синхронизация продаж завершена успешно',
                'stats': sales_synchronizer.stats
            })
            
        except Exception as e:
            import traceback
            error_message = str(e)
            app.logger.error(f"Sales sync error: {error_message}")
            app.logger.error(traceback.format_exc())
            return jsonify({'status': 'error', 'error': error_message}), 500
    
    # GET-запрос: отображение формы синхронизации
    session = Session()
    try:
        # Устанавливаем диапазон дат по умолчанию (последняя неделя)
        # Используем формат для datetime-local
        default_end_date = datetime.now().strftime('%Y-%m-%dT%H:%M')
        default_start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
        
        # Статистика для страницы
        total_sales = session.query(func.count(Sale.id)).scalar() or 0
        unique_orders = session.query(func.count(func.distinct(Sale.order_num))).scalar() or 0
        
        # Последняя продажа
        last_sale = session.query(Sale).order_by(Sale.close_time.desc()).first()
        last_sale_date = last_sale.close_time.strftime('%d.%m.%Y %H:%M') if last_sale and last_sale.close_time else None
        
        # Последняя синхронизация продаж
        last_sync = session.query(SyncLog).filter(SyncLog.entity_type == 'sales').order_by(SyncLog.sync_date.desc()).first()
        
        return render_template('sales_sync.html',
                             default_start_date=default_start_date,
                             default_end_date=default_end_date,
                             total_sales=total_sales,
                             unique_orders=unique_orders,
                             last_sale_date=last_sale_date,
                             last_sync=last_sync)
    finally:
        session.close()
        
@app.route('/writeoffs')
def writeoffs():
    """Список документов списания"""
    session = Session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Фильтры
        search = request.args.get('search', '')
        date_from = request.args.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))
        store_id = request.args.get('store_id', '')
        account_id = request.args.get('account_id', '')
        
        # Преобразуем строки даты в объекты datetime
        from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
        to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
        
        # Если указана to_date, добавляем 1 день для включения всего дня
        if to_date:
            to_date = to_date + timedelta(days=1)
        
        # Базовый запрос с join для получения названий склада и счета
        query = session.query(WriteoffDocument).join(Store, WriteoffDocument.store_id == Store.id, isouter=True).join(Account, WriteoffDocument.account_id == Account.id, isouter=True)
        
        # Применяем фильтры
        if from_date and to_date:
            query = query.filter(WriteoffDocument.date_incoming >= from_date, WriteoffDocument.date_incoming < to_date)
        
        if search:
            query = query.filter(or_(
                WriteoffDocument.document_number.ilike(f'%{search}%'),
                WriteoffDocument.comment.ilike(f'%{search}%') if WriteoffDocument.comment.isnot(None) else False
            ))
        
        if store_id:
            query = query.filter(WriteoffDocument.store_id == store_id)
            
        if account_id:
            query = query.filter(WriteoffDocument.account_id == account_id)
        
        # Подсчет общего количества и суммы
        total_count = query.count()
        
        # Получаем статистику по позициям
        items_subquery = session.query(
            WriteoffItem.document_id,
            func.count(WriteoffItem.id).label('items_count'),
            func.sum(WriteoffItem.amount).label('total_amount')
        ).group_by(WriteoffItem.document_id).subquery()
        
        # Пагинация с дополнительной информацией
        documents = query.outerjoin(items_subquery, WriteoffDocument.id == items_subquery.c.document_id)\
                         .add_columns(
                             Store.name.label('store_name'),
                             Account.name.label('account_name'),
                             items_subquery.c.items_count,
                             items_subquery.c.total_amount
                         )\
                         .order_by(WriteoffDocument.date_incoming.desc())\
                         .offset((page - 1) * per_page)\
                         .limit(per_page).all()
        
        # Получение списков для фильтров
        stores = session.query(Store).order_by(Store.name).all()
        accounts = session.query(Account).filter(Account.deleted == False).order_by(Account.name).all()
        
        template = 'writeoffs_content.html' if is_ajax_request() else 'writeoffs.html'
        return render_template(template, 
                             documents=documents,
                             page=page,
                             total_pages=(total_count + per_page - 1) // per_page,
                             total_count=total_count,
                             search=search,
                             date_from=date_from,
                             date_to=date_to,
                             store_id=store_id,
                             account_id=account_id,
                             stores=stores,
                             accounts=accounts)
    finally:
        session.close()

@app.route('/writeoff/<document_id>')
def writeoff_detail(document_id):
    """Детали документа списания"""
    session = Session()
    try:
        # Получаем документ с дополнительной информацией
        document = session.query(WriteoffDocument)\
                         .join(Store, WriteoffDocument.store_id == Store.id, isouter=True)\
                         .join(Account, WriteoffDocument.account_id == Account.id, isouter=True)\
                         .add_columns(
                             Store.name.label('store_name'),
                             Account.name.label('account_name')
                         )\
                         .filter(WriteoffDocument.id == document_id).first()
        
        if not document:
            return "Документ списания не найден", 404
        
        # Получаем позиции документа с информацией о продуктах
        items = session.query(WriteoffItem)\
                      .join(Product, WriteoffItem.product_id == Product.id, isouter=True)\
                      .add_columns(
                          Product.name.label('product_name'),
                          Product.code.label('product_code')
                      )\
                      .filter(WriteoffItem.document_id == document_id)\
                      .order_by(WriteoffItem.id).all()
        
        # Подсчитываем итоги
        total_items = len(items)
        total_amount = sum(item.WriteoffItem.amount or 0 for item in items)
        
        return render_template('writeoff_detail.html', 
                             document=document,
                             items=items,
                             total_items=total_items,
                             total_amount=total_amount)
    finally:
        session.close()

@app.route('/writeoffs/sync', methods=['GET', 'POST'])
def writeoffs_sync():
    """Страница синхронизации документов списания"""
    if request.method == 'POST':
        try:
            # Получаем параметры синхронизации
            data = request.json
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({
                    'status': 'error', 
                    'message': 'Необходимо указать даты начала и окончания'
                }), 400
            
            # Запуск синхронизации документов списания
            synchronizer = DataSynchronizer()
            result = synchronizer.sync_writeoff_documents(start_date, end_date)
            
            return jsonify({
                'status': 'success', 
                'message': 'Синхронизация документов списания завершена успешно',
                'stats': synchronizer.counters
            })
            
        except Exception as e:
            import traceback
            error_message = str(e)
            app.logger.error(f"Writeoffs sync error: {error_message}")
            app.logger.error(traceback.format_exc())
            return jsonify({'status': 'error', 'message': error_message}), 500
    
    # GET-запрос: отображение формы синхронизации
    session = Session()
    try:
        # Устанавливаем диапазон дат по умолчанию (последний месяц)
        default_end_date = datetime.now().strftime('%Y-%m-%d')
        default_start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Статистика для страницы
        total_documents = session.query(func.count(WriteoffDocument.id)).scalar() or 0
        total_items = session.query(func.count(WriteoffItem.id)).scalar() or 0
        
        # Последний документ
        last_document = session.query(WriteoffDocument).order_by(WriteoffDocument.date_incoming.desc()).first()
        last_document_date = last_document.date_incoming.strftime('%d.%m.%Y %H:%M') if last_document and last_document.date_incoming else None
        
        # Последняя синхронизация
        last_sync = session.query(SyncLog).filter(SyncLog.entity_type == 'writeoffs').order_by(SyncLog.sync_date.desc()).first()
        
        template = 'writeoffs_sync_content.html' if is_ajax_request() else 'writeoffs_sync.html'
        return render_template(template,
                             default_start_date=default_start_date,
                             default_end_date=default_end_date,
                             total_documents=total_documents,
                             total_items=total_items,
                             last_document_date=last_document_date,
                             last_sync=last_sync)
    finally:
        session.close()

@app.route('/writeoffs/delete', methods=['POST'])
def writeoffs_delete():
    """Удаление документов списания за период"""
    try:
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({
                'status': 'error', 
                'message': 'Необходимо указать даты начала и окончания'
            }), 400
        
        session = Session()
        try:
            # Преобразуем строки даты в объекты datetime
            from_date = datetime.strptime(start_date, '%Y-%m-%d')
            to_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            
            # Получаем документы для удаления
            documents_to_delete = session.query(WriteoffDocument)\
                                        .filter(WriteoffDocument.date_incoming >= from_date, 
                                               WriteoffDocument.date_incoming < to_date).all()
            
            deleted_docs = len(documents_to_delete)
            deleted_items = 0
            
            # Удаляем документы и их позиции
            for document in documents_to_delete:
                # Сначала удаляем позиции
                items = session.query(WriteoffItem).filter(WriteoffItem.document_id == document.id).all()
                deleted_items += len(items)
                for item in items:
                    session.delete(item)
                
                # Затем удаляем документ
                session.delete(document)
            
            session.commit()
            
            return jsonify({
                'status': 'success', 
                'message': f'Удалено {deleted_docs} документов и {deleted_items} позиций',
                'deleted_documents': deleted_docs,
                'deleted_items': deleted_items
            })
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    except Exception as e:
        import traceback
        error_message = str(e)
        app.logger.error(f"Writeoffs delete error: {error_message}")
        app.logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/sales/report')
def sales_report():
    """Отчет по продажам с группировкой"""
    return get_sales_report()



if __name__ == '__main__':
    # Создаем таблицы если их нет
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8080, debug=True)