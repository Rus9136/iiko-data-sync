#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta

# API endpoint
url = "http://127.0.0.1:8082/api/writeoff-reports"

# Test parameters
params = {
    "report_type": "writeoffs_by_period",
    "date_from": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
    "date_to": datetime.now().strftime('%Y-%m-%d'),
    "store_id": "",
    "account_id": "",
    "periodType": "month"
}

print(f"Testing API endpoint: {url}")
print(f"Parameters: {json.dumps(params, indent=2)}")

try:
    response = requests.post(url, json=params)
    print(f"\nResponse status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nResponse data: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"\nError response: {response.text}")
        
except Exception as e:
    print(f"\nError: {e}")