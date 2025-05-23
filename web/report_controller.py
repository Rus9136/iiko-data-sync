import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import request, jsonify, render_template, make_response, redirect, url_for

def get_sales_report():
    """
    Переадресация на новый модуль оперативной сводки
    """
    # Перенаправляем на новый интерфейс оперативной сводки
    return redirect('/operational-summary')