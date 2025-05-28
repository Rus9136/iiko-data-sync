#!/usr/bin/env python3
"""
Тест нового отчета 'Процент списаний от закупок'
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web.reports.writeoffs.writeoffs_reports_controller import get_writeoffs_data_internal
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_writeoffs_vs_procurement_report():
    """Тест отчета 'Процент списаний от закупок'"""
    print("=== Тестирование отчета 'Процент списаний от закупок' ===")
    
    # Параметры тестирования
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)  # Последние 30 дней
    
    filters = {
        'writeoffReportType': 'writeoffs_vs_procurement',
        'dateFrom': start_date,
        'dateTo': end_date,
        'store': 'all',
        'account': 'all'
    }
    
    print(f"Тестовые параметры:")
    print(f"  Период: с {start_date} по {end_date}")
    print(f"  Тип отчета: {filters['writeoffReportType']}")
    
    try:
        # Получаем данные отчета
        result = get_writeoffs_data_internal(filters)
        
        if result['success']:
            data = result['data']
            columns = result['columns']
            
            print(f"\n✅ Отчет успешно сгенерирован")
            print(f"📊 Количество записей: {len(data)}")
            print(f"📋 Колонки: {len(columns)}")
            
            # Выводим структуру колонок
            print(f"\n📋 Структура колонок:")
            for i, col in enumerate(columns):
                print(f"  {i+1}. {col['name']} ({col['key']}) - {col['type']}")
            
            # Выводим первые 5 записей
            if data:
                print(f"\n📈 Первые 5 записей:")
                for i, record in enumerate(data[:5]):
                    print(f"  Запись {i+1}:")
                    print(f"    Товар: {record.get('product_name', 'N/A')}")
                    print(f"    Код: {record.get('product_code', 'N/A')}")
                    print(f"    Поступило: {record.get('procurement_amount', 0):.3f}")
                    print(f"    Продано: {record.get('sold_amount', 0):.3f}")
                    print(f"    Списано: {record.get('writeoff_amount', 0):.3f}")
                    print(f"    % списаний: {record.get('writeoff_percentage', 0):.2f}%")
                    print(f"    Статус: {record.get('status', 'N/A')}")
                    print()
                
                # Статистика по статусам
                status_stats = {}
                total_procurement = 0
                total_writeoffs = 0
                
                for record in data:
                    status = record.get('status', 'Неопределен')
                    status_stats[status] = status_stats.get(status, 0) + 1
                    total_procurement += record.get('procurement_amount', 0)
                    total_writeoffs += record.get('writeoff_amount', 0)
                
                print(f"📊 Статистика по статусам:")
                for status, count in status_stats.items():
                    print(f"  {status}: {count} товаров")
                
                overall_percentage = (total_writeoffs / total_procurement * 100) if total_procurement > 0 else 0
                print(f"\n📈 Общая статистика:")
                print(f"  Общий объем поступлений: {total_procurement:.3f}")
                print(f"  Общий объем списаний: {total_writeoffs:.3f}")
                print(f"  Общий % списаний: {overall_percentage:.2f}%")
            else:
                print("⚠️  Данные отсутствуют")
            
        else:
            print(f"❌ Ошибка при генерации отчета: {result.get('error', 'Неизвестная ошибка')}")
            return False
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_writeoffs_vs_procurement_report()
    
    if success:
        print("\n✅ Тест завершен успешно!")
    else:
        print("\n❌ Тест завершен с ошибками!")
        sys.exit(1)