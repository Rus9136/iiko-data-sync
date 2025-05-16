#!/usr/bin/env python3
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, World! Flask is working."

if __name__ == '__main__':
    port = 8091
    print(f"Starting test Flask server on http://localhost:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)