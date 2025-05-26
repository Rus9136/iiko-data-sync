# Конфигурация отчетов
REPORTS_CONFIG = {
    'sales-by-period': {
        'id': 'sales-by-period',
        'name': 'Продажи по периодам',
        'category': 'sales',
        'filters': ['dateRange', 'department', 'store'],
        'columns': [
            {'key': 'date', 'name': 'Дата', 'type': 'date'},
            {'key': 'department', 'name': 'Отдел', 'type': 'string'},
            {'key': 'store', 'name': 'Точка продаж', 'type': 'string'},
            {'key': 'total_amount', 'name': 'Сумма продаж', 'type': 'money'},
            {'key': 'orders_count', 'name': 'Количество заказов', 'type': 'number'},
            {'key': 'avg_check', 'name': 'Средний чек', 'type': 'money'}
        ],
        'default_view': 'table',
        'allowed_views': ['table', 'chart'],
        'chart_type': 'line',
        'default_filters': {
            'dateRange': 'week',
            'department': 'all',
            'store': 'all'
        },
        'description': 'Анализ продаж по периодам с детализацией по отделам и точкам продаж'
    },
    'top-products': {
        'id': 'top-products',
        'name': 'Топ товаров',
        'category': 'products',
        'filters': ['dateRange', 'department', 'category', 'limit'],
        'columns': [
            {'key': 'product_name', 'name': 'Товар', 'type': 'string'},
            {'key': 'category', 'name': 'Категория', 'type': 'string'},
            {'key': 'total_amount', 'name': 'Сумма продаж', 'type': 'money'},
            {'key': 'quantity', 'name': 'Количество', 'type': 'number'},
            {'key': 'orders_count', 'name': 'Заказов', 'type': 'number'},
            {'key': 'abc_class', 'name': 'ABC класс', 'type': 'string'}
        ],
        'default_view': 'table',
        'allowed_views': ['table', 'chart'],
        'chart_type': 'bar',
        'default_filters': {
            'dateRange': 'month',
            'department': 'all',
            'category': 'all',
            'limit': 50
        },
        'description': 'Рейтинг товаров по продажам с ABC-анализом'
    },
    'writeoffs-by-period': {
        'id': 'writeoffs-by-period',
        'name': 'Списания по периодам',
        'category': 'writeoffs',
        'filters': ['dateRange', 'store', 'account'],
        'columns': [
            {'key': 'date', 'name': 'Дата', 'type': 'date'},
            {'key': 'store', 'name': 'Точка продаж', 'type': 'string'},
            {'key': 'account', 'name': 'Счет', 'type': 'string'},
            {'key': 'total_cost', 'name': 'Сумма списаний', 'type': 'money'},
            {'key': 'documents_count', 'name': 'Документов', 'type': 'number'},
            {'key': 'items_count', 'name': 'Позиций', 'type': 'number'}
        ],
        'default_view': 'table',
        'allowed_views': ['table', 'chart'],
        'chart_type': 'line',
        'default_filters': {
            'dateRange': 'month',
            'store': 'all',
            'account': 'all'
        },
        'description': 'Динамика списаний по периодам и счетам'
    },
    'departments-comparison': {
        'id': 'departments-comparison',
        'name': 'Сравнение точек продаж',
        'category': 'analytics',
        'filters': ['dateRange', 'department'],
        'columns': [
            {'key': 'department', 'name': 'Отдел', 'type': 'string'},
            {'key': 'total_sales', 'name': 'Продажи', 'type': 'money'},
            {'key': 'total_writeoffs', 'name': 'Списания', 'type': 'money'},
            {'key': 'efficiency', 'name': 'Эффективность %', 'type': 'percent'},
            {'key': 'avg_check', 'name': 'Средний чек', 'type': 'money'},
            {'key': 'orders_count', 'name': 'Заказов', 'type': 'number'}
        ],
        'default_view': 'table',
        'allowed_views': ['table', 'chart'],
        'chart_type': 'bar',
        'default_filters': {
            'dateRange': 'month',
            'department': 'all'
        },
        'description': 'Сравнительный анализ эффективности отделов'
    }
}

# Конфигурация фильтров
FILTERS_CONFIG = {
    'dateRange': {
        'type': 'dateRange',
        'name': 'Период',
        'presets': [
            {'key': 'today', 'name': 'Сегодня'},
            {'key': 'yesterday', 'name': 'Вчера'},
            {'key': 'week', 'name': 'Неделя'},
            {'key': 'month', 'name': 'Месяц'},
            {'key': 'quarter', 'name': 'Квартал'},
            {'key': 'year', 'name': 'Год'},
            {'key': 'custom', 'name': 'Произвольный период'}
        ]
    },
    'department': {
        'type': 'select',
        'name': 'Отдел',
        'multiple': True,
        'source': 'departments',
        'default_option': {'value': 'all', 'text': 'Все отделы'}
    },
    'store': {
        'type': 'select',
        'name': 'Точка продаж',
        'multiple': True,
        'source': 'stores',
        'default_option': {'value': 'all', 'text': 'Все точки продаж'}
    },
    'category': {
        'type': 'select',
        'name': 'Категория',
        'multiple': True,
        'source': 'categories',
        'hierarchical': True,
        'default_option': {'value': 'all', 'text': 'Все категории'}
    },
    'product': {
        'type': 'select',
        'name': 'Товар',
        'multiple': True,
        'source': 'products',
        'searchable': True,
        'depends_on': 'category',
        'default_option': {'value': 'all', 'text': 'Все товары'}
    },
    'account': {
        'type': 'select',
        'name': 'Счет',
        'multiple': True,
        'source': 'accounts',
        'hierarchical': True,
        'default_option': {'value': 'all', 'text': 'Все счета'}
    },
    'limit': {
        'type': 'number',
        'name': 'Лимит записей',
        'min': 10,
        'max': 1000,
        'step': 10,
        'default': 50
    }
}

# Категории отчетов для группировки в меню
REPORT_CATEGORIES = {
    'sales': {
        'name': 'Продажи',
        'icon': 'fas fa-chart-line',
        'order': 1
    },
    'products': {
        'name': 'Товары',
        'icon': 'fas fa-box',
        'order': 2
    },
    'writeoffs': {
        'name': 'Списания',
        'icon': 'fas fa-minus-circle',
        'order': 3
    },
    'analytics': {
        'name': 'Аналитика',
        'icon': 'fas fa-chart-bar',
        'order': 4
    }
}