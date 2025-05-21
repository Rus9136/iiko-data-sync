import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

from src.models import Base, Product, Category, SyncLog, Store
from src.synchronizer import DataSynchronizer
from src.store_synchronizer import StoreSynchronizer
from config.config import DATABASE_CONFIG

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
        
        # Последняя синхронизация (берем самую позднюю между продуктами и складами)
        last_sync_products = session.query(SyncLog).filter(SyncLog.entity_type == 'products').order_by(SyncLog.sync_date.desc()).first()
        last_sync_stores = session.query(SyncLog).filter(SyncLog.entity_type == 'stores').order_by(SyncLog.sync_date.desc()).first()
        
        if last_sync_products and last_sync_stores:
            last_sync = last_sync_products if last_sync_products.sync_date > last_sync_stores.sync_date else last_sync_stores
        else:
            last_sync = last_sync_products or last_sync_stores
        
        return render_template('index.html', 
                             total_products=total_products,
                             active_products=active_products,
                             deleted_products=deleted_products,
                             total_stores=total_stores,
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

if __name__ == '__main__':
    # Создаем таблицы если их нет
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8080, debug=True)