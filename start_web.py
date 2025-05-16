#!/usr/bin/env python3
"""
Запуск веб-интерфейса IIKO Data Sync
"""
import sys
import os
import webbrowser
import time
import threading

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    """Открывает браузер через 2 секунды после запуска"""
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8080')

if __name__ == '__main__':
    from web.app import app
    
    print("🚀 Запуск веб-интерфейса IIKO Data Sync...")
    print("📍 Сервер будет доступен по адресу: http://127.0.0.1:8080")
    print("🌐 Браузер откроется автоматически через 2 секунды")
    print("\n⚠️  Для остановки сервера нажмите Ctrl+C\n")
    
    # Запускаем браузер в отдельном потоке
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Запускаем Flask
    app.run(host='127.0.0.1', port=8080, debug=False)