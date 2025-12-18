import sqlite3
import os

DB_FILE = "audit_data.db"

def test_db_logic():
    print(f"Testing DB: {DB_FILE}")
    if not os.path.exists(DB_FILE):
        print("ERROR: DB file not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Check Groups
    print("--- GROUPS ---")
    c.execute("SELECT id, name FROM groups")
    groups = c.fetchall()
    for g in groups:
        print(f"ID: {g[0]}, Name: '{g[1]}'")
        
    if not groups:
        print("No groups found in DB.")
        conn.close()
        return

    # 2. Test get_all_group_names
    print("\n--- TEST get_all_group_names ---")
    c.execute("SELECT name FROM groups ORDER BY name ASC")
    names = [r[0] for r in c.fetchall()]
    print(f"Names found: {names}")
    
    # 3. Test load_group_data for each name
    print("\n--- TEST load_group_data ---")
    for name in names:
        print(f"Loading '{name}'...")
        c.execute("SELECT id FROM groups WHERE name = ?", (name,))
        row = c.fetchone()
        if row:
            print(f"  -> Found ID: {row[0]}")
            c.execute("SELECT COUNT(*) FROM members WHERE group_id=?", (row[0],))
            count = c.fetchone()[0]
            print(f"  -> Members count: {count}")
        else:
            print(f"  -> ERROR: Could not find group by name '{name}'")
            
    conn.close()

if __name__ == "__main__":
    test_db_logic()
