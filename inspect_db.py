import sqlite3
import pandas as pd

DB_FILE = "BaseDatosXM.db"

try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if trsd exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trsd'")
    if not cursor.fetchone():
        print("Table 'trsd' does not exist.")
        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("Tables found:", [t[0] for t in cursor.fetchall()])
    else:
        cursor.execute("PRAGMA table_info('trsd')")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Columns in trsd: {cols}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
