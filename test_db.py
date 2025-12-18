import sqlite3
import os
from datetime import datetime
import pandas as pd

DB_FILE = "audit_data.db"

def test_db_init():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    # Import functions from main (assuming we will update main.py to have these)
    # For now, we will test the structure we plan to write
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create Tables
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    name TEXT,
                    photo_path TEXT,
                    joined_date DATE,
                    FOREIGN KEY(group_id) REFERENCES groups(id)
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS audit_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    month TEXT,
                    year INTEGER,
                    is_finalized BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, month, year)
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    member_id INTEGER,
                    cash_today INTEGER,
                    fines INTEGER,
                    savings_bf INTEGER,
                    savings_today INTEGER,
                    savings_cf INTEGER,
                    loan_bf INTEGER,
                    loan_principal INTEGER,
                    loan_interest INTEGER,
                    loan_cf INTEGER,
                    advance_bf INTEGER,
                    advance_principal INTEGER,
                    advance_interest INTEGER,
                    advance_cf INTEGER,
                    FOREIGN KEY(session_id) REFERENCES audit_sessions(id),
                    FOREIGN KEY(member_id) REFERENCES members(id)
                )''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def test_workflow():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Create Group
    c.execute("INSERT INTO groups (name) VALUES ('Test Group')")
    group_id = c.lastrowid
    print(f"✅ Group Created: ID {group_id}")
    
    # 2. Add Member
    c.execute("INSERT INTO members (group_id, name) VALUES (?, ?)", (group_id, "Alice"))
    member_id = c.lastrowid
    print(f"✅ Member Created: ID {member_id}")
    
    # 3. Save Session (Month 1)
    c.execute("INSERT INTO audit_sessions (group_id, month, year, is_finalized) VALUES (?, ?, ?, 1)", (group_id, 'January', 2025))
    session_id = c.lastrowid
    
    c.execute('''INSERT INTO transactions 
                 (session_id, member_id, cash_today, savings_cf, loan_cf, advance_cf) 
                 VALUES (?, ?, 1000, 500, 200, 0)''', 
                 (session_id, member_id))
    conn.commit()
    print("✅ Session 1 Saved")
    
    # 4. Carry Forward (Check Previous Data)
    # Simulate fetching previous month data
    c.execute('''SELECT t.savings_cf, t.loan_cf, t.advance_cf 
                 FROM transactions t 
                 JOIN audit_sessions s ON t.session_id = s.id 
                 WHERE s.group_id = ? AND s.month = ? AND s.year = ? AND t.member_id = ?''',
                 (group_id, 'January', 2025, member_id))
    row = c.fetchone()
    if row == (500, 200, 0):
        print("✅ Carry Forward Verification Passed")
    else:
        print(f"❌ Carry Forward Failed: Got {row}")
        
    conn.close()

if __name__ == "__main__":
    test_db_init()
    test_workflow()
