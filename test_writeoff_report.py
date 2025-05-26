#!/usr/bin/env python3

import requests
import json
from datetime import datetime, timedelta

# Test writeoff reports API
url = "http://127.0.0.1:8082/api/writeoff-reports"

# Prepare test data
today = datetime.now()
date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
date_to = today.strftime('%Y-%m-%d')

test_params = {
    "report_type": "writeoffs_by_period",
    "date_from": date_from,
    "date_to": date_to,
    "store_id": "",
    "account_id": "",
    "periodType": "day",
    "showDynamics": "true"
}

print("Testing writeoff reports API...")
print(f"URL: {url}")
print(f"Params: {json.dumps(test_params, indent=2)}")

try:
    response = requests.post(url, json=test_params)
    print(f"\nResponse status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nResponse data:")
        print(f"Status: {data.get('status')}")
        print(f"Total records: {data.get('total_records', 0)}")
        if 'data' in data:
            print(f"Data records: {len(data['data'])}")
            if data['data']:
                print(f"First record: {data['data'][0]}")
        if 'columns' in data:
            print(f"Columns: {[col['title'] for col in data['columns']]}")
    else:
        print(f"\nError response: {response.text}")
        
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")