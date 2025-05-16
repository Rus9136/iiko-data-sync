#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

# Get database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'iiko_data')
DB_USER = os.getenv('DB_USER', 'rus')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

print(f"Trying to connect to database: {DB_NAME} on {DB_HOST}:{DB_PORT} as user {DB_USER}")

try:
    # Establish a connection
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    
    tables = cursor.fetchall()
    print("Available tables:")
    for table in tables:
        print(f"- {table[0]}")
    
    # Close cursor and connection
    cursor.close()
    conn.close()
    
    print("Database connection test successful!")
    
except Exception as e:
    print(f"Error connecting to the database: {e}")
    sys.exit(1)