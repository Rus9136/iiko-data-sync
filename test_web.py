#!/usr/bin/env python3
import requests
import time
import sys

# URL to test
url = "http://localhost:8092/"

print(f"Attempting to connect to {url}")

max_attempts = 3
attempts = 0

while attempts < max_attempts:
    attempts += 1
    print(f"Attempt {attempts}/{max_attempts}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        print(f"Response length: {len(response.text)} bytes")
        if response.status_code == 200:
            print("Connected successfully!")
            print("First 100 characters of response:")
            print(response.text[:100])
            sys.exit(0)
        else:
            print(f"Server responded with error code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("Connection refused - server may not be running")
    except requests.exceptions.Timeout:
        print("Connection timed out")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    if attempts < max_attempts:
        print("Waiting 2 seconds before retrying...")
        time.sleep(2)

print("Failed to connect after multiple attempts.")
sys.exit(1)