#!/usr/bin/env python3
"""
Основной скрипт для запуска веб-интерфейса IIKO Data Sync
"""
import os
import sys
import webbrowser
import time
import threading

# Добавляем путь к проекту
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def open_browser():
    """Открывает браузер через 2 секунды после запуска"""
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8080')

if __name__ == '__main__':
    from web.app import app
    
    port = 8080
    host = '127.0.0.1'
    
    print(f"🚀 Запуск веб-интерфейса IIKO Data Sync...")
    print(f"📍 Сервер будет доступен по адресу: http://{host}:{port}")
    print(f"🌐 Браузер откроется автоматически через 2 секунды")
    print(f"\n⚠️  Для остановки сервера нажмите Ctrl+C\n")
    
    # Запускаем браузер в отдельном потоке
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Запускаем Flask
    app.run(host=host, port=port, debug=False)