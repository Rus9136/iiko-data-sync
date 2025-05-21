import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from sqlalchemy import create_engine, func, desc, or_, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

from src.models import Base, Product, Category, SyncLog, Store, Sale
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
        
        # Последняя синхронизация (берем самую позднюю)
        last_sync_products = session.query(SyncLog).filter(SyncLog.entity_type == 'products').order_by(SyncLog.sync_date.desc()).first()
        last_sync_stores = session.query(SyncLog).filter(SyncLog.entity_type == 'stores').order_by(SyncLog.sync_date.desc()).first()
        last_sync_sales = session.query(SyncLog).filter(SyncLog.entity_type == 'sales').order_by(SyncLog.sync_date.desc()).first()
        
        # Находим самую позднюю синхронизацию среди всех типов
        all_syncs = [s for s in [last_sync_products, last_sync_stores, last_sync_sales] if s is not None]
        last_sync = max(all_syncs, key=lambda x: x.sync_date) if all_syncs else None
        
        return render_template('index.html', 
                             total_products=total_products,
                             active_products=active_products,
                             deleted_products=deleted_products,
                             total_stores=total_stores,
                             total_sales=total_sales,
                             last_sync=last_sync)
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
        
        return render_template('products.html', 
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
        
        return render_template('stores.html', 
                             stores=stores_data,
                             page=page,
                             total_pages=(total + per_page - 1) // per_page,
                             total=total,
                             search=search)
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
        
        return render_template('product_detail.html', 
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
        
        return render_template('store_detail.html', 
                             store=store,
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
        return render_template('logs.html', logs=logs)
    finally:
        session.close()

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Загрузка JSON файла с данными"""
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
    return render_template('upload.html')

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route('/sales')
def sales():
    """Список продаж"""
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
        
        # Базовый запрос
        query = session.query(Sale)
        
        # Применяем фильтры
        if from_date and to_date:
            query = query.filter(Sale.close_time >= from_date, Sale.close_time < to_date)
        
        if search:
            query = query.filter(or_(
                Sale.dish_name.ilike(f'%{search}%'),
                Sale.fiscal_cheque_number.ilike(f'%{search}%'),
                Sale.dish_code.ilike(f'%{search}%'),
                Sale.order_num.cast(String).ilike(f'%{search}%')
            ))
        
        if store_id:
            query = query.filter(Sale.store_id == store_id)
            
        # Добавляем фильтр по типу чека
        sale_type = request.args.get('sale_type', 'all')
        if sale_type == 'normal':
            # Обычные продажи (не отменены, не возвраты)
            query = query.filter(
                Sale.storned == False, 
                or_(Sale.dish_return_sum == 0, Sale.dish_return_sum == None)
            )
        elif sale_type == 'returns':
            # Возвраты
            query = query.filter(
                or_(Sale.dish_return_sum > 0, and_(Sale.dish_return_sum != None, Sale.dish_return_sum > 0))
            )
        elif sale_type == 'canceled':
            # Отмененные чеки
            query = query.filter(Sale.storned == True)
        
        # Статистика для текущего запроса
        total_count = query.count()
        
        # Использование func.sum для подсчета сумм
        total_sum_query = session.query(func.sum(Sale.dish_sum)).filter(query.whereclause)
        discount_sum_query = session.query(func.sum(Sale.dish_discount_sum)).filter(query.whereclause)
        
        total_sum = total_sum_query.scalar() or 0
        discount_sum = discount_sum_query.scalar() or 0
        
        # Получение уникальных заказов
        unique_orders_query = session.query(func.count(func.distinct(Sale.order_num))).filter(query.whereclause)
        unique_orders = unique_orders_query.scalar() or 0
        
        # Пагинация
        sales = query.order_by(Sale.close_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
        
        # Получение списка складов для фильтра
        stores = session.query(Store).order_by(Store.name).all()
        
        return render_template('sales.html', 
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
    """Детали продажи"""
    session = Session()
    try:
        sale = session.query(Sale).filter_by(id=sale_id).first()
        if not sale:
            return "Продажа не найдена", 404
        
        # Получаем другие товары в том же заказе
        related_sales = session.query(Sale).filter(
            Sale.order_num == sale.order_num,
            Sale.fiscal_cheque_number == sale.fiscal_cheque_number
        ).all()
        
        # Подсчитываем общую сумму для чека
        total_sum = sum(related.dish_sum or 0 for related in related_sales if related.dish_sum is not None)
        total_discount = sum(related.dish_discount_sum or 0 for related in related_sales if related.dish_discount_sum is not None)
        
        return render_template('sale_detail.html', 
                             sale=sale,
                             related_sales=related_sales,
                             total_sum=total_sum,
                             total_discount=total_discount)
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
        
@app.route('/sales/report')
def sales_report():
    """Отчет по продажам с группировкой"""
    return get_sales_report()

if __name__ == '__main__':
    # Создаем таблицы если их нет
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8080, debug=True)