import streamlit as st
import pandas as pd
from fpdf import FPDF
import sqlite3
import io
from datetime import datetime

# --- 0. Page Config & CSS ---
st.set_page_config(layout="wide", page_title="Jirani")

st.markdown("""
<style>
    /* Hide spin buttons in WebKit/Blink (Chrome, Safari, Edge) */
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {
        -webkit-appearance: none !important;
        margin: 0 !important;
    }
    /* Hide spin buttons in Firefox */
    input[type="number"] {
        -moz-appearance: textfield !important;
    }
    
    /* Reduce glare on dataframe selection and headers */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
    }
    .stDataFrame div[data-testid="stVerticalBlock"] {
        background-color: transparent;
    }
    /* Hide index if visible */
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)

# --- 1. Database Setup & Helpers ---

DB_FILE = "audit_data.db"

# --- Constants ---
FINE_LATE = 50
FINE_ABSENT = 100
FINE_APOLOGY = 20

def init_db():
    """Initializes the SQLite database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Groups Table
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # Members Table
    c.execute('''CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    name TEXT,
                    photo_path TEXT,
                    joined_date DATE,
                    photo_path TEXT,

                    account_number TEXT UNIQUE,
                    phone TEXT,
                    id_number TEXT,
                    email TEXT,
                    residence TEXT,
                    sponsor_name TEXT,
                    next_of_kin TEXT,
                    role TEXT DEFAULT 'Member',
                    
                    national_id TEXT,
                    kra_pin TEXT,
                    dob TEXT,
                    gender TEXT,
                    occupation TEXT,
                    next_of_kin_name TEXT,
                    next_of_kin_phone TEXT,
                    
                    FOREIGN KEY(group_id) REFERENCES groups(id)
                )''')
    
    # Simple migration check for existing databases
    try:
        c.execute("ALTER TABLE members ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE members ADD COLUMN id_number TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE members ADD COLUMN next_of_kin TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE members ADD COLUMN account_number INTEGER UNIQUE")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE members ADD COLUMN role TEXT DEFAULT 'Member'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE members ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE members ADD COLUMN residence TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE members ADD COLUMN sponsor_name TEXT")
    except sqlite3.OperationalError:
        pass
                
    # Audit Sessions Table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    month TEXT,
                    year INTEGER,
                    is_finalized BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, month, year)
                )''')
    
    # Transactions Table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    member_id INTEGER,
                    cash_today INTEGER DEFAULT 0,
                    fines INTEGER DEFAULT 0,
                    savings_bf INTEGER DEFAULT 0,
                    savings_today INTEGER DEFAULT 0,
                    savings_cf INTEGER DEFAULT 0,
                    loan_bf INTEGER DEFAULT 0,
                    loan_principal INTEGER DEFAULT 0,
                    loan_interest INTEGER DEFAULT 0,
                    loan_cf INTEGER DEFAULT 0,
                    advance_bf INTEGER DEFAULT 0,
                    advance_principal INTEGER DEFAULT 0,
                    advance_interest INTEGER DEFAULT 0,
                    advance_cf INTEGER DEFAULT 0,
                    attendance_status TEXT DEFAULT 'Present',
                    new_loan INTEGER DEFAULT 0,
                    new_advance INTEGER DEFAULT 0,
                    savings_withdrawal INTEGER DEFAULT 0,
                    guarantors TEXT,
                    loan_image TEXT,
                    FOREIGN KEY(session_id) REFERENCES audit_sessions(id),
                    FOREIGN KEY(member_id) REFERENCES members(id)
                )''')
    
    # Migration for members table (if legacy DB exists)
    try:
        c.execute("ALTER TABLE members ADD COLUMN account_number INTEGER")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE members ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE members ADD COLUMN id_number TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE members ADD COLUMN next_of_kin TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE members ADD COLUMN photo_path TEXT")
    except sqlite3.OperationalError:
        pass
        
    # Migration for Deep KYC
    new_cols = ['national_id', 'kra_pin', 'dob', 'gender', 'occupation', 'next_of_kin_name', 'next_of_kin_phone']
    for col in new_cols:
        try:
            c.execute(f"ALTER TABLE members ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # Migration for attendance_status
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN attendance_status TEXT DEFAULT 'Present'")
    except sqlite3.OperationalError:
        pass
        
    # Migration for new_loan (Allocation Stage)
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN new_loan INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Migration for bank_balance_closing (Audit Sessions)
    try:
        c.execute("ALTER TABLE audit_sessions ADD COLUMN bank_balance_closing INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    # Migration for groups table (next_meeting_date)
    try:
        c.execute("ALTER TABLE groups ADD COLUMN next_meeting_date TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Migration for guarantors and loan_image
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN guarantors TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN loan_image TEXT")
    except sqlite3.OperationalError:
        pass

    # Migration for new_advance and savings_withdrawal
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN new_advance INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE transactions ADD COLUMN savings_withdrawal INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()


import random

def generate_account_number():
    """Generates a unique 6-digit account number."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    while True:
        # Generate 6-digit string
        acc_num = str(random.randint(100000, 999999))
        c.execute("SELECT id FROM members WHERE account_number = ?", (acc_num,))
        if not c.fetchone():
            conn.close()
            return acc_num
    
def get_all_groups_extended():
    """Returns a list of dicts: {'id': id, 'name': name, 'meeting_date': date_str} sorted by date."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Handle legacy cases where next_meeting_date might be NULL -> treat as far future
    c.execute("SELECT id, name, next_meeting_date FROM groups ORDER BY next_meeting_date ASC")
    rows = c.fetchall()
    conn.close()
    
    groups = []
    for r in rows:
        groups.append({
            'id': r[0],
            'name': r[1],
            'meeting_date': r[2] if r[2] else "9999-12-31" # Sort nulls last
        })
    
    # Sort again in python to be safe with string dates
    groups.sort(key=lambda x: x['meeting_date'])
    return groups

def load_group_data(group_id):
    """
    Loads members by GROUP ID (not name, for safety).
    Returns: (group_name, members_list) 
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, []
        
    group_name = row[0]
    
    c.execute("SELECT id, name FROM members WHERE group_id = ?", (group_id,))
    members = c.fetchall()
    
    conn.close()
    return group_name, members

def create_new_group(name, member_names, first_meeting_date):
    """Creates a new group and its initial members."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO groups (name, next_meeting_date) VALUES (?, ?)", 
                  (name, str(first_meeting_date)))
        group_id = c.lastrowid
        conn.commit() # Commit group first so FK works
        conn.close() # Close to be safe, though add_member opens its own
        
        for m_name in member_names:
            # Use add_member helper to ensure consistency
            # Pass defaults for new KYC fields
            add_member(group_id, m_name.strip(), phone="", id_num="")
        
        return group_id
    except sqlite3.IntegrityError:
        if conn: conn.close()
        return None # Name exists
    except Exception as e:
        print(e)
        if conn: conn.close()
        return None

def save_session(group_id, month, year, df, bank_close=0):
    """Saves the audit session data to the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if session exists
    c.execute("SELECT id FROM audit_sessions WHERE group_id = ? AND month = ? AND year = ?", (group_id, month, year))
    row = c.fetchone()
    
    if row:
        session_id = row[0]
        # Update existing session finalize status and bank balance
        c.execute("UPDATE audit_sessions SET is_finalized = 1, bank_balance_closing = ? WHERE id = ?", (bank_close, session_id))
        # Clear old transactions to replace them (simplest way to handle updates)
        c.execute("DELETE FROM transactions WHERE session_id = ?", (session_id,))
    else:
        # Create new session
        c.execute("INSERT INTO audit_sessions (group_id, month, year, is_finalized, bank_balance_closing) VALUES (?, ?, ?, 1, ?)", 
                  (group_id, month, year, bank_close))
        session_id = c.lastrowid
        
    # 2. Insert Transactions
    # df should have 'Member ID' and all financial columns
    for _, row in df.iterrows():
        # Ensure fallback to defaults if NaN or missing
        def get_val(key):
            try:
                val = row[key]
                return int(float(val)) if pd.notnull(val) else 0
            except (ValueError, KeyError):
                return 0
                
        c.execute('''INSERT INTO transactions (
                        session_id, member_id, 
                        cash_today, fines, 
                        savings_bf, savings_today, savings_cf,
                        loan_bf, loan_principal, loan_interest, loan_cf,
                        advance_bf, advance_principal, advance_interest, advance_cf,
                        attendance_status, new_loan, new_advance, savings_withdrawal, guarantors, loan_image
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (session_id, row['Member ID'],
                   get_val('Total Cash Today'), get_val('Fines'),
                   get_val('Savings BF'), get_val('Savings Today'), get_val('Savings CF'),
                   get_val('Loan BF'), get_val('Loan Principal'), get_val('Loan Interest'), get_val('Loan CF'),
                   get_val('Advance BF'), get_val('Advance Principal'), get_val('Advance Interest'), get_val('Advance CF'),
                   row.get('Attendance', 'Present'),
                   get_val('New Loan'), get_val('New Advance'), get_val('Savings Withdrawal'),
                   row.get('Guarantors'), row.get('Loan Image')
                  ))
    
    conn.commit()
    conn.close()
    return session_id

def get_previous_month_data(group_id, current_month, current_year):
    """
    Finds the most recent finalized session BEFORE the current month/year.
    For strict 'Previous Month' logic, we calculate expected prev month.
    Returns: DataFrame containing CF values renamed to BF, or None.
    """
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    
    try:
        curr_idx = months.index(current_month)
        if curr_idx == 0:
            prev_month = "December"
            prev_year = current_year - 1
        else:
            prev_month = months[curr_idx - 1]
            prev_year = current_year
    except ValueError:
        return None

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Find session ID
    c.execute("SELECT id FROM audit_sessions WHERE group_id=? AND month=? AND year=? AND is_finalized=1", 
              (group_id, prev_month, prev_year))
    res = c.fetchone()
    
    if not res:
        conn.close()
        return None
        
    session_id = res[0]
    
    # Fetch Data
    query = '''
        SELECT m.name, m.id, 
               t.savings_cf, t.loan_cf, t.advance_cf
        FROM transactions t
        JOIN members m ON t.member_id = m.id
        WHERE t.session_id = ?
    '''
    c.execute(query, (session_id,))
    rows = c.fetchall()
    conn.close()
    
    # Create DF with "BF" columns mapped from "CF"
    data = []
    for r in rows:
        # r: name, id, sav_cf, loan_cf, adv_cf
        data.append({
            'Member Name': r[0],
            'Member ID': r[1],
            'Savings BF': r[2],
            'Loan BF': r[3],
            'Advance BF': r[4]
        })
        
    return pd.DataFrame(data)

def get_audit_history(group_id):
    """Returns list of all finalized sessions for a group."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, month, year, created_at FROM audit_sessions WHERE group_id=? AND is_finalized=1 ORDER BY created_at DESC", (group_id,))
    rows = c.fetchall()
    conn.close()
    return rows
    
def get_previous_bank_balance(group_id, current_month, current_year):
    """
    Retrieves the closing bank balance from the LAST finalized session.
    It does NOT require strict consecutive months (handles skipped months).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get all finalized sessions for this group
    c.execute("SELECT month, year, bank_balance_closing FROM audit_sessions WHERE group_id=? AND is_finalized=1", (group_id,))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return 0
        
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
              
    # Convert current to comparable value (Year * 12 + MonthIndex)
    try:
        curr_val = current_year * 12 + months.index(current_month)
    except ValueError:
        return 0
        
    # Filter and Sort
    valid_Sessions = []
    for r in rows:
        m_str, y_int, bal = r
        try:
            m_idx = months.index(m_str)
            s_val = y_int * 12 + m_idx
            
            # Only consider sessions BEFORE the current one
            if s_val < curr_val:
                valid_Sessions.append((s_val, bal))
        except ValueError:
            continue
            
    if not valid_Sessions:
        return 0
        
    # Sort by date descending (latest first)
    valid_Sessions.sort(key=lambda x: x[0], reverse=True)
    
    return int(valid_Sessions[0][1])

def load_full_session_data(session_id):
    """Loads all transaction data + attendance for a session."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = '''
        SELECT m.name, m.id,
               t.cash_today, t.fines,
               t.savings_bf, t.savings_today, t.savings_cf,
               t.loan_bf, t.loan_principal, t.loan_interest, t.loan_cf,
               t.advance_bf, t.advance_principal, t.advance_interest, t.advance_cf,
               t.attendance_status, t.new_loan, t.new_advance, t.savings_withdrawal, t.guarantors, t.loan_image
        FROM transactions t
        JOIN members m ON t.member_id = m.id
        WHERE t.session_id = ?
    '''
    c.execute(query, (session_id,))
    rows = c.fetchall()
    conn.close()
    
    cols = [
        'Member Name', 'Member ID', 
        'Total Cash Today', 'Fines', 
        'Savings BF', 'Savings Today', 'Savings CF',
        'Loan BF', 'Loan Principal', 'Loan Interest', 'Loan CF',
        'Advance BF', 'Advance Principal', 'Advance Interest', 'Advance CF',
        'Attendance', 'New Loan', 'New Advance', 'Savings Withdrawal', 'Guarantors', 'Loan Image'
    ]
    return pd.DataFrame(rows, columns=cols)

def get_member_details(member_id):
    """Fetches all details for a specific member."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE id = ?", (member_id,))
    row = c.fetchone()
    # row: id, group_id, name, photo_path, joined_date, phone, id_number, next_of_kin
    if row:
        # Get column names
        cols = [description[0] for description in c.description]
        return dict(zip(cols, row))
    return None

def update_member_details(member_id, phone, id_num, kin, photo_path=None):
    """Updates member profile."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    query = "UPDATE members SET phone=?, id_number=?, next_of_kin=?"
    params = [phone, id_num, kin]
    
    if photo_path:
        query += ", photo_path=?"
        params.append(photo_path)
        
    query += " WHERE id=?"
    params.append(member_id)
    
    c.execute(query, tuple(params))
    conn.commit()
    conn.commit()
    conn.close()

def update_member_role(member_id, new_role):
    """Updates member role (Admin only)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE members SET role = ? WHERE id = ?", (new_role, member_id))
    conn.commit()
    conn.close()

import os
def save_uploaded_file(uploaded_file, member_id):
    """Saves uploaded photo to assets/profiles."""
    if not os.path.exists("assets/profiles"):
        os.makedirs("assets/profiles")
    
    ext = uploaded_file.name.split('.')[-1]
    fname = f"member_{member_id}.{ext}"
    path = os.path.join("assets/profiles", fname)
    
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    return path

    return path

def add_member(group_id, name, phone, id_num, email=None, residence=None, sponsor=None,
               kra_pin=None, dob=None, gender=None, occupation=None, 
               next_of_kin_name=None, next_of_kin_phone=None):
    """Adds a new member."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    acc_num = generate_account_number()
    try:
        c.execute('''INSERT INTO members (
            group_id, name, joined_date, account_number, phone, id_number, 
            email, residence, sponsor_name,
            kra_pin, dob, gender, occupation, next_of_kin_name, next_of_kin_phone
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
          (group_id, name, datetime.now().date(), acc_num, phone, id_num, 
           email, residence, sponsor,
           kra_pin, dob, gender, occupation, next_of_kin_name, next_of_kin_phone))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding member: {e}")
        return False
    finally:
        conn.close()

def check_if_guarantor(name):
    """Checks if a member (by Name) is listed as a guarantor."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Simple substring check (ideal world would use IDs, but requirement is Text names)
    c.execute("SELECT id FROM transactions WHERE guarantors LIKE ?", (f"%{name}%",))
    res = c.fetchone()
    conn.close()
    return res is not None

def delete_member(member_id):
    """Deletes a member."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()

def save_loan_image(uploaded_file, transaction_id):
    """Saves loan image."""
    if not os.path.exists("assets/loans"):
        os.makedirs("assets/loans")
    
    ext = uploaded_file.name.split('.')[-1]
    fname = f"loan_{transaction_id}.{ext}"
    path = os.path.join("assets/loans", fname)
    
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    # Update DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE transactions SET loan_image = ? WHERE id = ?", (path, transaction_id))
    conn.commit()
    conn.close()
    return path

def check_loan_eligibility(status):
    """Returns True if member is eligible for loan (Present or Late)."""
    return status in ["Present", "Late"]

def get_active_loans(group_id):
    """Fetches active loans/advances for the group."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = '''
        SELECT t.id, m.name, s.month, s.year, t.loan_principal, t.advance_principal, t.guarantors, t.loan_image
        FROM transactions t
        JOIN members m ON t.member_id = m.id
        JOIN audit_sessions s ON t.session_id = s.id
        WHERE s.group_id = ? AND (t.loan_principal > 0 OR t.advance_principal > 0)
        ORDER BY s.year DESC, s.id DESC
    '''
    c.execute(query, (group_id,))
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        amt = r[4] if r[4] > 0 else r[5]
        type_str = "Loan" if r[4] > 0 else "Advance"
        data.append({
            'Transaction ID': r[0],
            'Borrower': r[1],
            'Date': f"{r[2]} {r[3]}",
            'Type': type_str,
            'Amount': amt,
            'Guarantors': r[6] if r[6] else "None",
            'Image': r[7]
        })
    return pd.DataFrame(data)

# --- 2. State & Data Logic ---

def init_empty_dataframe(members_list):
    """Creates a fresh dataframe for the session with 0s."""
    cols = [
        'Member Name', 'Member ID', 
        'Total Cash Today', 'Fines', 
        'Savings BF', 'Savings Today', 'Savings CF',
        'Loan BF', 'Loan Principal', 'Loan Interest', 'Loan CF',
        'Advance BF', 'Advance Principal', 'Advance Interest', 'Advance CF',
        'Attendance', 'New Loan', 'New Advance', 'Savings Withdrawal', 'Guarantors', 'Loan Image'
    ]
    df = pd.DataFrame(columns=cols)
    
    names = [m[1] for m in members_list]
    ids = [m[0] for m in members_list]
    
    df['Member Name'] = names
    df['Member ID'] = ids
    df['Attendance'] = "Present"
    
    for c in cols[2:-4]: # Skip Member info, Attendance, New Loan, New Adv, Savings W/D, Guarantors (handled separately)
       pass 
    
    # Initialize numeric columns explicitly
    numeric_defaults = [
        'Total Cash Today', 'Fines', 
        'Savings BF', 'Savings Today', 'Savings CF',
        'Loan BF', 'Loan Principal', 'Loan Interest', 'Loan CF',
        'Advance BF', 'Advance Principal', 'Advance Interest', 'Advance CF',
        'New Loan', 'New Advance', 'Savings Withdrawal'
    ]
    for c in numeric_defaults:
        df[c] = 0
    return df

def merge_carry_forward(empty_df, prev_df):
    """Merges previous month balances into the new empty dataframe."""
    # prev_df has: Member ID, Savings BF, Loan BF, Advance BF (mapped from CF)
    
    # We use Member ID as key to map
    empty_df = empty_df.set_index('Member ID')
    prev_df = prev_df.set_index('Member ID')
    
    # Update matched indices
    for col in ['Savings BF', 'Loan BF', 'Advance BF']:
        if col in prev_df.columns:
            empty_df[col].update(prev_df[col])
            
    return empty_df.reset_index()

def round_to_five(n):
    """Rounds a number to the nearest 5."""
    return 5 * round(n / 5)

def calculate_waterfall(idx):
    """Performs financial calculations for a single row."""
    df = st.session_state.audit_df
    
    # Helper to safely get int
    def get_int(col):
        try:
            return int(float(df.at[idx, col]))
        except:
            return 0

    adv_bf = get_int('Advance BF')
    loan_bf = get_int('Loan BF')
    fines = get_int('Fines')
    loan_prin = get_int('Loan Principal')
    adv_prin = get_int('Advance Principal')
    cash_today = get_int('Total Cash Today')
    
    # Logic
    # Apply rounding to interest:
    adv_int_raw = adv_bf * 0.10
    loan_int_raw = loan_bf * 0.015
    
    adv_int = int(round_to_five(adv_int_raw))
    loan_int = int(round_to_five(loan_int_raw))
    
    # Write interest FIRST so it's included in calculations if needed,
    # or just stored. Logic: Deductions include Interest.
    df.at[idx, 'Advance Interest'] = adv_int
    df.at[idx, 'Loan Interest'] = loan_int
    
    deductions = fines + loan_prin + loan_int + adv_prin + adv_int
    savings_today = cash_today - deductions
    
    # Write back results
    df.at[idx, 'Savings Today'] = savings_today
    
    sav_bf = get_int('Savings BF')
    df.at[idx, 'Savings CF'] = sav_bf + savings_today
    
    new_loan = get_int('New Loan')
    df.at[idx, 'Loan CF'] = loan_bf - loan_prin + new_loan
    df.at[idx, 'Advance CF'] = adv_bf - adv_prin
    
    st.session_state.audit_df = df

def update_val(col):
    """Input callback."""
    idx = st.session_state.current_member_index
    m = st.session_state.get('audit_month', 'NA')
    y = st.session_state.get('audit_year', 'NA')
    stage = st.session_state.get('audit_stage', 'collection')
    key = f"{col}_{idx}_{m}_{y}_{stage}"
    
    if key in st.session_state:
        st.session_state.audit_df.at[idx, col] = st.session_state[key]

def update_attendance_fines():
    """Updates fines based on attendance."""
    idx = st.session_state.current_member_index
    status = st.session_state.get(f"attend_{idx}", "Present")
    
    # Update Status in DF
    st.session_state.audit_df.at[idx, 'Attendance'] = status
    
    # Auto-Fine Logic
    fine = 0
    if status == "Late":
        fine = FINE_LATE
    elif status == "Absent":
        fine = FINE_ABSENT
    elif status == "Apology":
        fine = FINE_APOLOGY
        
    # Update Fine in DF and Input
    st.session_state.audit_df.at[idx, 'Fines'] = fine
    
    # Crucial: Update the number_input session state key to reflect change immediately
    m = st.session_state.get('audit_month', 'NA')
    y = st.session_state.get('audit_year', 'NA')
    stage = st.session_state.get('audit_stage', 'collection')
    fine_key = f"Fines_{idx}_{m}_{y}_{stage}"
    st.session_state[fine_key] = fine

# --- 3. Reporting PDF ---
# --- 3. Reporting PDF ---
class PDF(FPDF):
    def header(self):
        # Color: Navy (30, 60, 100)
        self.set_text_color(30, 60, 100)
        self.set_font('Arial', 'B', 16)
        title = f"{st.session_state.group_name}"
        self.cell(0, 10, title, 0, 1, 'L')
        
        # Color: Teal (0, 150, 150)
        self.set_text_color(0, 150, 150)
        self.set_font('Arial', 'B', 12)
        subtitle = f"Audit Report | {st.session_state.audit_month} {st.session_state.audit_year}"
        self.cell(0, 8, subtitle, 0, 1, 'L')
        self.ln(5)
        
        # Reset to black
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()} - Generated by Group Audit Tool', 0, 0, 'C')

    def section_title(self, label):
        self.set_fill_color(240, 240, 240) # Light Grey
        self.set_text_color(0, 150, 150) # Teal
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, f"  {label}", 0, 1, 'L', fill=True)
        self.ln(2)
        self.set_text_color(0, 0, 0)
        
    def financial_summary(self, data):
        self.set_font('Arial', '', 10)
        
        # Box for Stats
        self.set_draw_color(0, 150, 150)
        self.set_line_width(0.5)
        
        # Row 1
        self.cell(60, 8, f"Total Cash Collected: {data['cash_in']:,}", 0, 0)
        self.cell(60, 8, f"Bank Reserve (BF): {data['bank_bf']:,}", 0, 1)
        
        # Row 2
        self.cell(60, 8, f"Total New Loans: {data['new_loans']:,}", 0, 0)
        
        if data['withdrawal'] > 0:
            self.set_text_color(200, 0, 0) # Red warning
            self.cell(60, 8, f"Withdrawn from Reserve: {data['withdrawal']:,}", 0, 1)
        else:
             self.set_text_color(0, 100, 0)
             self.cell(60, 8, f"Deposited to Reserve: {data['to_bank']:,}", 0, 1)
        
        self.set_text_color(0, 0, 0)
        
        # Row 3 (Ext Borrowing)
        if data['ext_borrowing'] > 0:
            self.set_text_color(255, 0, 0)
            self.cell(60, 8, f"External Borrowing: {data['ext_borrowing']:,}", 0, 1)
        else:
             self.cell(60, 8, "External Borrowing: 0", 0, 1)
             
        self.set_text_color(0,0,0)
        self.ln(5)

    def attendance_summary(self, counts):
        self.set_font('Arial', '', 10)
        self.cell(40, 8, f"Present: {counts.get('Present', 0)}", 0, 0)
        self.cell(40, 8, f"Late: {counts.get('Late', 0)}", 0, 0)
        self.cell(40, 8, f"Absent: {counts.get('Absent', 0)}", 0, 1)
        self.ln(5)

    def master_ledger(self, df):
        # Columns: Acct No, Name, Attend, Sav In, Loan Repaid, New Loan, Fines
        # Widths
        w_acct = 25
        w_name = 45
        w_att = 25
        w_sav = 25
        w_rep = 25
        w_new = 25
        w_fine = 20
        
        # Header
        self.set_fill_color(30, 60, 100) # Navy
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 9)
        
        self.cell(w_acct, 7, "Acct No", 1, 0, 'C', True)
        self.cell(w_name, 7, "Name", 1, 0, 'L', True)
        self.cell(w_att, 7, "Status", 1, 0, 'C', True)
        self.cell(w_sav, 7, "Savings", 1, 0, 'R', True)
        self.cell(w_rep, 7, "Repaid", 1, 0, 'R', True)
        self.cell(w_new, 7, "New Loan", 1, 0, 'R', True)
        self.cell(w_fine, 7, "Fines", 1, 1, 'R', True)
        
        # Rows
        self.set_text_color(0, 0, 0)
        self.set_font('Arial', '', 9)
        self.set_fill_color(240, 240, 240) # Light Grey
        
        fill = False
        
        for idx, row in df.iterrows():
            mid = row['Member ID']
            d = get_member_details(int(mid))
            acc = str(d.get('account_number', 'N/A'))
            
            # Safe extraction helper
            def get_safe_int(key):
                try:
                    val = row.get(key, 0)
                    return int(float(val)) if pd.notnull(val) else 0
                except:
                    return 0

            repaid = get_safe_int('Loan Principal') + get_safe_int('Advance Principal')
            sav_today = get_safe_int('Savings Today')
            nl = get_safe_int('New Loan')
            fine = get_safe_int('Fines')
            
            self.cell(w_acct, 6, acc, 1, 0, 'C', fill)
            self.cell(w_name, 6, str(row['Member Name'])[:22], 1, 0, 'L', fill)
            self.cell(w_att, 6, str(row.get('Attendance', '')), 1, 0, 'C', fill)
            
            self.cell(w_sav, 6, f"{sav_today:,}", 1, 0, 'R', fill)
            self.cell(w_rep, 6, f"{repaid:,}", 1, 0, 'R', fill)
            self.cell(w_new, 6, f"{nl:,}", 1, 0, 'R', fill)
            self.cell(w_fine, 6, f"{fine:,}", 1, 1, 'R', fill)
            
            fill = not fill # Toggle stripe
            self.ln()

def generate_pdf_report():
    """Generates the upgraded PDF report."""
    # 1. Sanitize Dataframe
    # Create clean copy and fill ALL NaNs with 0 (User Request)
    clean_df = st.session_state.audit_df.copy()
    clean_df.fillna(0, inplace=True)
    
    # Ensure numeric columns are strictly integers for cleaner display/calculations
    numeric_cols = ['Total Cash Today', 'Savings Today', 'Loan Principal', 'Loan Interest', 
                    'Advance Principal', 'Advance Interest', 'New Loan', 'Fines', 
                    'Savings BF', 'Loan BF', 'Advance BF']
    
    for c in numeric_cols:
        if c in clean_df.columns:
            # Coerce to number (handles empty strings), fill any resulting NaNs with 0, convert to int
            clean_df[c] = pd.to_numeric(clean_df[c], errors='coerce').fillna(0).astype(int)
            
    # 2. Calculate Banking Metrics
    bank_bf = st.session_state.bank_balance_bf
    
    cash_in = int(clean_df['Total Cash Today'].sum())
    new_loans = int(clean_df['New Loan'].sum())
    
    gap = cash_in - new_loans
    
    to_bank = 0
    withdrawal = 0
    ext_borrowing = 0
    
    if gap >= 0:
        to_bank = gap
    else:
        deficit = abs(gap)
        if bank_bf >= deficit:
            withdrawal = deficit
        else:
            withdrawal = bank_bf
            ext_borrowing = deficit - withdrawal
            
    fin_data = {
        'cash_in': cash_in,
        'bank_bf': bank_bf,
        'new_loans': new_loans,
        'to_bank': to_bank,
        'withdrawal': withdrawal,
        'ext_borrowing': ext_borrowing
    }
    
    # 3. Attendance Counts
    if 'Attendance' in clean_df.columns:
        attend_counts = clean_df['Attendance'].value_counts().to_dict()
    else:
        attend_counts = {}
    
    # 4. Generate PDF
    pdf = PDF()
    pdf.add_page()
    
    # Section A
    pdf.section_title("Financial Executive Summary")
    pdf.financial_summary(fin_data)
    
    # Section B
    pdf.section_title("Attendance Summary")
    pdf.attendance_summary(attend_counts)
    
    # Section C
    pdf.section_title("Master Ledger")
    # Pass cleanliness is next to godliness
    pdf.master_ledger(clean_df)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. Main UI Flow ---

# Initialize DB
init_db()

# Initialize Session State
state_keys = {
    'setup_complete': False,
    'current_member_index': 0,
    'audit_df': pd.DataFrame(),
    'group_name': "",
    'group_id': None,
    'audit_month': "",
    'audit_year': 2025,
    'info_msg': "",
    'show_navigation': False,
    'viewing_profile': False,
    'audit_stage': 'collection', # collection | allocation
    'bank_balance_bf': 0, # New: Cumulative Banking
    'viewing_global_stats': False,
    'audit_stage': 'collection', # collection | allocation
    'bank_balance_bf': 0, # New: Cumulative Banking
    'viewing_global_stats': False,
    'viewing_admin': False,
    'admin_selected_group_id': None
}

for k, v in state_keys.items():
    if k not in st.session_state:
        st.session_state[k] = v

months_list = ["January", "February", "March", "April", "May", "June", 
               "July", "August", "September", "October", "November", "December"]

# --- SETUP / LANDING ---
# --- SETUP / LANDING ---
def view_global_stats():
    st.markdown("## 📊 Global Ecosystem Statistics")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Total Groups
    c.execute("SELECT COUNT(*) FROM groups")
    total_groups = c.fetchone()[0]
    
    # 2. Financials
    c.execute("SELECT SUM(cash_today), SUM(loan_principal) FROM transactions")
    row = c.fetchone()
    total_cash = row[0] if row[0] else 0
    total_loans = row[1] if row[1] else 0
    
    conn.close()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Groups", total_groups)
    c2.metric("Total Liquidity (Cash In)", f"{total_cash:,}")
    c3.metric("Total Loans Issued", f"{total_loans:,}")
    
    st.divider()
    if st.button("⬅️ Back to Home"):
        st.session_state.viewing_global_stats = False
        st.rerun()

def get_member_attendance_history(member_id):
    """Fetches attendance history for a member."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = '''
        SELECT s.month, s.year, t.attendance_status
        FROM transactions t
        JOIN audit_sessions s ON t.session_id = s.id
        WHERE t.member_id = ?
        ORDER BY s.year DESC, s.id DESC
    '''
    c.execute(query, (member_id,))
    rows = c.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=['Month', 'Year', 'Status'])

# --- 3. View Helpers (Strict Separation) ---

def render_attendance_view(group_id, group_name):
    st.divider()
    st.subheader("📋 Step 1: Attendance Register")
    
    # 1. Prepare Logic Display Data
    # We construct a temporary dataframe specifically for the editor
    # This includes: Name, Account Number (fetched), Status
    
    # Ensure base audit_df has 'Attendance' initialized
    if 'Attendance' not in st.session_state.audit_df.columns:
        st.session_state.audit_df['Attendance'] = "Present"
        
    # Helper to fetch account number efficiently
    def get_acc(mid):
        try:
            d = get_member_details(mid)
            return d.get('account_number', 'N/A')
        except:
            return 'N/A'
            
    # Build Display DF
    display_data = []
    # Build Display DF - Explicitly typed
    for idx, row in st.session_state.audit_df.iterrows():
        display_data.append({
            "Member ID": str(row['Member ID']), # Hidden key
            "Name": str(row['Member Name']),
            "Account Number": str(get_acc(row['Member ID'])),
            "Attendance Status": "Present" # FORCE FILL for Dropdown
        })
        
    display_df = pd.DataFrame(display_data)
    
    # 2. Render Editor
    updated_df = st.data_editor(
        display_df[["Name", "Account Number", "Attendance Status"]], # Explicit columns
        column_order=["Name", "Account Number", "Attendance Status"],
        column_config={
            "Name": st.column_config.TextColumn("Member Name", disabled=True),
            "Account Number": st.column_config.TextColumn("Account No", disabled=True),
            "Attendance Status": st.column_config.SelectboxColumn(
                "Attendance Status",
                options=["Present", "Late", "Absent", "Apology"],
                required=True,
                width="medium"
            )
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="attendance_final_fix"
    )
    
    # 3. Confirm Logic
    if st.button("✅ Confirm Attendance & Proceed", type="primary"):
        # Iterate and Update Main DF
        # We assume the order matches because we built it from iterrows
        # But to be safe, we can map by Member ID if needed. 
        # For simplicity and speed in this specific flow, implicit order is usually fine if not sorted by user.
        # But 'updated_df' preserves index from 'display_df' which is 0..N.
        
        # Create map for O(1) update
        # Because we only show 3 columns, we rely on implicit index or we need to join back to ID
        # Since 'display_df' was created in order of 'audit_df', 'updated_df' preserves that order.
        # We can map updated statuses back to original IDs using index.
        
        status_map = {}
        for idx, row in updated_df.iterrows():
             # We need to map row index to Member ID from original df
             # The updated_df has same index as display_df, which matches audit_df iteration order
             # BUT safest is to grab ID if we had it. We didn't include it in editor view?
             # We excluded it from 'display_df[["Name" ...]]' above.
             # So we must rely on index alignment.
             
             original_mid = st.session_state.audit_df.iloc[idx]['Member ID']
             status_map[original_mid] = row['Attendance Status']
        
        # Save to session record as requested
        st.session_state.attendance_record = status_map # Simplified map

        
        # Update Audit DF
        for idx, row in st.session_state.audit_df.iterrows():
            mid = row['Member ID']
            new_status = status_map.get(mid, 'Present')
            
            st.session_state.audit_df.at[idx, 'Attendance'] = new_status
            
            # Auto-Fine
            fine = 0
            if new_status == "Late":
                fine = FINE_LATE
            elif new_status == "Absent":
                fine = FINE_ABSENT
            elif new_status == "Apology":
                fine = FINE_APOLOGY
                
            st.session_state.audit_df.at[idx, 'Fines'] = fine
            
        # Transition
        st.session_state.audit_stage = "collection"
        st.success("Attendance Recorded! Fines Applied.")
        st.rerun()

def render_dashboard_common(stage):
    """Shared logic for Collection and Allocation views."""
    
    # 1. Calculate Live Aggregates
    df_calc = st.session_state.audit_df.copy()
    numeric_cols = ['Total Cash Today', 'Savings Today', 'Loan Principal', 'Loan Interest', 
                    'Advance Principal', 'Advance Interest', 'New Loan', 'New Advance', 'Savings Withdrawal',
                    'Fines', 'Savings BF', 'Loan BF', 'Advance BF']
    for c in numeric_cols:
         if c in df_calc.columns:
             df_calc[c] = pd.to_numeric(df_calc[c], errors='coerce').fillna(0)
             
    total_cash_in = int(df_calc['Total Cash Today'].sum())
    total_new_loan = int(df_calc['New Loan'].sum())
    total_new_advance = int(df_calc['New Advance'].sum())
    total_withdrawal = int(df_calc['Savings Withdrawal'].sum())
    
    total_money_out = total_new_loan + total_new_advance + total_withdrawal
    
    # Deficit/Surplus Logic
    bank_bf = st.session_state.bank_balance_bf
    cash_today = total_cash_in
    money_out_req = total_money_out
    
    operational_gap = cash_today - money_out_req
    
    # Init variables
    to_bank = 0
    withdraw_from_bank = 0
    external_borrowing = 0
    new_bank_balance = bank_bf + operational_gap # Simplistic starting point
    
    # Detailed Gap Logic
    if operational_gap >= 0:
        to_bank = operational_gap
        # new_bank_balance is correct (BF + Net Positive)
    else:
        deficit = abs(operational_gap)
        if bank_bf >= deficit:
            withdraw_from_bank = deficit
            # new_bank_balance is correct (BF - Deficit)
        else:
            withdraw_from_bank = bank_bf
            external_borrowing = deficit - withdraw_from_bank
            new_bank_balance = 0

    st.session_state.calculated_bank_close = new_bank_balance

    # --- Top Navigation ---
    c_head, c_nav = st.columns([3, 1])
    c_head.header(f"{st.session_state.group_name} | {st.session_state.audit_month} {st.session_state.audit_year}")
    
    with c_nav:
        if stage == "collection":
            if st.button("➡️ Next: Allocation", type="primary", use_container_width=True, key="action_collection_top"):
                st.session_state.audit_stage = "allocation"
                st.rerun()
                
        elif stage == "allocation":
             if st.button("💾 Finish Audit", type="primary", use_container_width=True, key="action_finalize_top"):
                save_session(st.session_state.group_id, 
                             st.session_state.audit_month, 
                             st.session_state.audit_year, 
                             st.session_state.audit_df,
                             new_bank_balance)
                st.session_state.show_navigation = True
                st.success(f"Finalized! Bank: {new_bank_balance:,}")
                st.rerun()
             
    # Utility Toolbar
    c_util1, c_util2, c_util3 = st.columns(3)
    with c_util1:
        if st.button("📂 History", use_container_width=True, key=f"hist_btn_{stage}"):
            @st.dialog("Audit History")
            def show_history():
                sessions = get_audit_history(st.session_state.group_id)
                if not sessions:
                    st.warning("No history found.")
                    return
                for s in sessions:
                    sid, m, y, cat = s
                    if st.button(f"{m} {y} (Saved: {cat})", key=f"hist_{sid}"):
                        st.session_state.history_view_id = sid
                        st.rerun()
                if 'history_view_id' in st.session_state:
                    st.divider()
                    st.write(f"Viewing Session ID: {st.session_state.history_view_id}")
                    hdf = load_full_session_data(st.session_state.history_view_id)
                    st.dataframe(hdf, hide_index=True)
            show_history()
    with c_util2:
        if st.button("📄 Report", use_container_width=True, key=f"rpt_btn_{stage}"):
            pdf_data = generate_pdf_report()
            st.download_button("Download PDF", data=pdf_data, file_name="report.pdf", mime="application/pdf")
    with c_util3:
        if st.button("Exit", use_container_width=True, key=f"exit_btn_{stage}"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    
    # --- 2. Member & Metrics View ---
    left, right = st.columns([1, 3], gap="medium")
    
    # --- LEFT COLUMN: Profile + Inputs ---
    with left:
        idx = st.session_state.current_member_index
        if idx >= len(st.session_state.audit_df):
            idx = 0
            st.session_state.current_member_index = 0
            
        cur_name = st.session_state.audit_df.at[idx, 'Member Name']
        cur_mid = int(st.session_state.audit_df.at[idx, 'Member ID'])
        
        # Load Photo
        mem_details = get_member_details(cur_mid)
        photo_path = mem_details.get('photo_path')
        display_img = "https://www.w3schools.com/howto/img_avatar.png"
        if photo_path and os.path.exists(photo_path):
            display_img = photo_path
        
        # Profile Card
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([1, 4, 1])
            col_a.button("⬅️", disabled=(idx==0), key=f"prev_{stage}", on_click=lambda: st.session_state.update(current_member_index=idx-1))
            
            with col_b:
                st.image(display_img, use_container_width=True)
                st.markdown(f"<h4 style='text-align:center; margin-top:5px'>{cur_name}</h4>", unsafe_allow_html=True)
                
            col_c.button("➡️", disabled=(idx==len(st.session_state.audit_df)-1), key=f"next_{stage}", on_click=lambda: st.session_state.update(current_member_index=idx+1))
            
            if st.button("📄 View Full Profile", use_container_width=True, key=f"prof_{stage}"):
                st.session_state.viewing_profile = True
                st.rerun()
        
        st.divider()

        # Inputs
        st.write("#### 📝 Inputs")

        if stage == "collection":
            # Attendance Selector
            cur_attend = st.session_state.audit_df.at[idx, 'Attendance']
            is_eligible = check_loan_eligibility(cur_attend)
            status_color = "red" if not is_eligible else "green"
            st.markdown(f"Status: **:{status_color}[{cur_attend}]**")
            
            input_config = [
                ("Total Cash Today", "Total Cash Today"),
                ("Savings Today", "Savings Today"),
                ("Loan Interest", "Loan Interest Paid"),
                ("Fines", "Fines"),
                ("Advance Principal", "Advance Principal Paid"),
                ("Loan Principal", "Loan Principal Paid")
            ]
            
            for col_name, label in input_config:
                 val = st.session_state.audit_df.at[idx, col_name]
                 if pd.isna(val): val = 0
                 key_w = f"{col_name}_{idx}_{st.session_state.audit_month}_{st.session_state.audit_year}_{stage}"
                 st.number_input(label, value=int(val), step=1, key=key_w, on_change=update_val, args=(col_name,))

            st.divider()
            if st.button("Calculate", type="primary", use_container_width=True, key=f"calc_{stage}"):
                calculate_waterfall(idx)

        else:
            # ALLOCATION PHASE INPUTS
            st.info("🏦 Allocation Phase")
            
            # Section A: Borrowing
            st.caption("Section A: Borrowing")
            
            # New Advance
            val_adv = st.session_state.audit_df.at[idx, 'New Advance']
            if pd.isna(val_adv): val_adv = 0
            st.number_input("New Advance", value=int(val_adv), step=1, key=f"new_adv_{idx}", on_change=update_val, args=('New Advance',))

            # New Loan
            val_loan = st.session_state.audit_df.at[idx, 'New Loan']
            if pd.isna(val_loan): val_loan = 0
            st.number_input("New Loan", value=int(val_loan), step=1, key=f"new_loan_{idx}", on_change=update_val, args=('New Loan',))
            
            # Guarantors
            all_members = st.session_state.audit_df['Member Name'].tolist()
            potential_guarantors = [m for m in all_members if m != cur_name]
            
            current_g_str = st.session_state.audit_df.at[idx, 'Guarantors']
            if pd.isna(current_g_str) or current_g_str == 0: 
                current_g_str = ""
            current_g_list = [x.strip() for x in str(current_g_str).split(",") if x.strip()]
            # Filter valid
            current_g_list = [x for x in current_g_list if x in potential_guarantors]
            
            sel_guarantors = st.multiselect("Guarantors", potential_guarantors, default=current_g_list, key=f"guar_{idx}")
            
            # Update Guarantors directly
            st.session_state.audit_df.at[idx, 'Guarantors'] = ", ".join(sel_guarantors)

            st.write("---")
            # Section B: Withdrawal
            st.caption("Section B: Withdrawal")
            
            # Validation Logic
            sav_bf = st.session_state.audit_df.at[idx, 'Savings BF']
            sav_today = st.session_state.audit_df.at[idx, 'Savings Today']
            max_withdraw = (sav_bf if pd.notnull(sav_bf) else 0) + (sav_today if pd.notnull(sav_today) else 0)
            
            val_wd = st.session_state.audit_df.at[idx, 'Savings Withdrawal']
            if pd.isna(val_wd): val_wd = 0
            
            wd_input = st.number_input("Savings Withdrawal", value=int(val_wd), step=1, key=f"wd_{idx}", on_change=update_val, args=('Savings Withdrawal',))
            
            if wd_input > max_withdraw:
                st.warning(f"⚠️ Creates Negative Savings! Max: {max_withdraw}")
            else:
                st.caption(f"Max Withdrawable: {max_withdraw}")

            st.write("---")
            # Save Button for Allocation
            if st.button(f"💾 Save Allocation for {cur_name}", key=f"save_alloc_{idx}", use_container_width=True):
                # Since we use on_change callbacks, the session state is already updated (st.session_state.audit_df).
                # We just need to give visual feedback that it is 'done' for this user.
                # In a real app with instant DB syncing, we might flush here.
                # For this session-df based app, the data is already in the DF.
                st.success(f"Allocation for {cur_name} confirmed!")
                
    # --- RIGHT COLUMN: Ledger + Metrics ---
    with right:
        # 1. Live Financial Overview (Top)
        st.subheader("Live Money Out Overview" if stage == "allocation" else "Live Financial Overview")
        
        if stage == "collection":
             st.info("💰 Collection Phase: Input Cash, Fines, and Repayments.")
             m1, m2 = st.columns(2)
             m1.metric("Total Cash Collected", f"{total_cash_in:,}", delta="Pool Available")
             st.write("When ready, click **Next: Allocation** in the top right.")
                  
        else:
             st.success("💸 Allocation Phase: Manage Loans, Advances, and Withdrawals.")
             st.markdown(f"**🏦 Bank Reserve (BF):** `{bank_bf:,}`")
             
             m1, m2, m3, m4 = st.columns(4)
             m1.metric("Cash Pool", f"{cash_today:,}", help="Total collected today")
             m2.metric("New Loans", f"{total_new_loan:,}", delta="Money Out", delta_color="inverse")
             m3.metric("New Advances", f"{total_new_advance:,}", delta="Money Out", delta_color="inverse")
             m4.metric("Withdrawals", f"{total_withdrawal:,}", delta="Money Out", delta_color="inverse")
             
             st.divider()
             
             k1, k2, k3 = st.columns(3)
             k1.metric("Total Money Out", f"{total_money_out:,}", delta_color="inverse")
             k2.metric("Operational Gap", f"{operational_gap:,}", delta_color="normal" if operational_gap >= 0 else "inverse")
             k3.metric("New Bank Balance", f"{new_bank_balance:,}")

             if external_borrowing > 0:
                st.error(f"⚠️ CAP CRITICAL: External Borrowing Needed: {external_borrowing:,}")
             elif withdraw_from_bank > 0:
                 st.warning(f"📉 Deficit Covered by Reserve. Withdrawing: {withdraw_from_bank:,}")
             else:
                 st.success(f"📈 Surplus! Adding {to_bank:,} to Reserve.")
             
        st.divider()

        # 2. Master Ledger (Bottom)
        st.subheader("Master Ledger" if stage == "collection" else "Allocation Table")
        
        # Prepare Display Data
        # Placeholder BF = 0
        df_calc['Savings BF'] = 0
        df_calc['Advance BF'] = 0
        df_calc['Loan BF'] = 0
        
        # Calculate CF
        df_calc['Savings CF'] = df_calc['Savings BF'] + df_calc['Savings Today']
        df_calc['Advance CF'] = df_calc['Advance BF'] - df_calc['Advance Principal']
        df_calc['Loan CF'] = df_calc['Loan BF'] - df_calc['Loan Principal']
        
        if stage == "collection":
            # Exact Column Order for Collection
            target_order = [
                'Member Name', 'Total Cash Today', 
                'Savings BF', 'Savings Today', 'Savings CF', 
                'Advance BF', 'Advance Principal', 'Advance CF', 
                'Loan BF', 'Loan Interest', 'Loan Principal', 'Loan CF'
            ]
        else:
            # Column Order for Allocation
            target_order = [
                'Member Name', 'New Loan', 'New Advance', 'Savings Withdrawal', 'Guarantors'
            ]
        
        # Filter strictly
        final_cols = [c for c in target_order if c in df_calc.columns]
        
        st.dataframe(df_calc[final_cols], use_container_width=True, height=400)


def render_collection_view(group_id):
    render_dashboard_common("collection")

def render_allocation_view(group_id):
    render_dashboard_common("allocation")

def view_admin_panel():
    st.markdown("## ⚙️ Administration Panel")
    
    # --- Layer 1: Group Grid (Default) ---
    if st.session_state.admin_selected_group_id is None:
        if st.button("⬅️ Back to Home", key="admin_back_home"):
            st.session_state.viewing_admin = False
            st.rerun()
            
        st.divider()
        st.subheader("Select a Group to Manage")
        
        all_groups = get_all_groups_extended()
        if not all_groups:
            st.warning("No groups found. Create one on the home screen.")
            return

        cols = st.columns(3)
        for i, group in enumerate(all_groups):
            col = cols[i % 3]
            # ID, Name, Meeting
            gid = group['id']
            with col:
                 if st.button(f"📁 {group['name']}", key=f"g_btn_{gid}", use_container_width=True):
                     st.session_state.admin_selected_group_id = gid
                     st.rerun()
                     
    # --- Layer 2 & 3: Group Detail & Drill Down ---
    else:
        # Load Group logic
        gid = st.session_state.admin_selected_group_id
        g_name, members_tuples = load_group_data(gid)
        
        # Header
        c1, c2 = st.columns([1, 5])
        if c1.button("⬅️ Back", key="admin_back_grid"):
            st.session_state.admin_selected_group_id = None
            st.rerun()
            
        c2.markdown(f"### Managing: **{g_name}**")
        st.divider()
        
        # Tabs for Group Management
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "👥 Manage Members", "📂 Loan Portfolio"])
        
        # --- Tab 1: Dashboard (Existing Logic) ---
        with tab1:
            st.markdown("#### 🏛️ Leadership Team")
            
            # We need full member details to filter by role
            # members_tuples is just (id, name). fetch details for all.
            full_members = []
            leaders = []
            
            for mid, mname in members_tuples:
                d = get_member_details(mid)
                role = d.get('role', 'Member')
                # Append dict for dataframe later
                full_members.append({
                    'ID': mid,
                    'Name': mname,
                    'Role': role,
                    'Account No': d.get('account_number'),
                    'Phone': d.get('phone')
                })
                
                if role in ['Chairman', 'Secretary', 'Treasurer']:
                    leaders.append((mname, role))
            
            if leaders:
                l_cols = st.columns(len(leaders))
                for idx, (lname, lrole) in enumerate(leaders):
                    with l_cols[idx]:
                        st.info(f"**{lrole}**\n\n{lname}")
            else:
                st.caption("No leadership roles assigned yet.")
                
            st.divider()
            
            st.markdown("#### 👥 Member Directory")
            df_mem = pd.DataFrame(full_members)
            
            if not df_mem.empty:
                st.dataframe(df_mem[['Name', 'Role', 'Account No', 'Phone', 'ID']], hide_index=True, use_container_width=True)
            
                # Update Role UI
                with st.expander("🛠️ Update Member Role", expanded=False):
                    c_mem, c_role, c_btn = st.columns([2, 2, 1])
                    
                    m_map = {m['Name']: m['ID'] for m in full_members}
                    sel_name = c_mem.selectbox("Select Member", list(m_map.keys()), key="adm_sel_mem")
                    
                    # Default index
                    # Find current role
                    curr_role = next((m['Role'] for m in full_members if m['Name'] == sel_name), 'Member')
                    roles = ["Member", "Chairman", "Secretary", "Treasurer"]
                    
                    new_role = c_role.selectbox("New Role", roles, index=roles.index(curr_role) if curr_role in roles else 0, key="adm_sel_role")
                    
                    if c_btn.button("Update", key="adm_update_btn"):
                        update_member_role(m_map[sel_name], new_role)
                        st.success(f"Updated {sel_name}!")
                        st.rerun()

            st.divider()

            # Member Inspector
            st.markdown("#### 🔍 Member Inspector (Drill-Down)")
            if not df_mem.empty:
                insp_name = st.selectbox("Select Member to Inspect", list(m_map.keys()), key="adm_insp_mem")
                if insp_name:
                    mid = m_map[insp_name]
                    hist_df = get_member_attendance_history(mid)
                    
                    if not hist_df.empty:
                        st.write(f"**Activity History for {insp_name}:**")
                        st.dataframe(hist_df, use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No activity found for {insp_name}.")

        # --- Tab 2: Manage Members ---
        with tab2:
            st.subheader("Add New Member")
            with st.form("add_member_form", clear_on_submit=True):
                st.markdown("### ➕ Add New Member (Deep KYC)")
                
                # SECTION 1: CORE KYC
                st.caption("Core Identity")
                name_in = st.text_input("Full Name *")
                
                c_a1, c_a2 = st.columns(2)
                id_num_in = c_a1.text_input("ID / Passport Number *")
                kra_pin_in = c_a2.text_input("KRA PIN")
                
                c_b1, c_b2, c_b3 = st.columns(3)
                dob_in = c_b1.date_input("Date of Birth", value=None)
                gender_in = c_b2.selectbox("Gender", ["Select...", "Male", "Female"], index=0)
                occu_in = c_b3.text_input("Occupation")

                # SECTION 2: CONTACT & LOCATION
                st.caption("Contact & Location")
                c_c1, c_c2 = st.columns(2)
                phone_in = c_c1.text_input("Phone Number")
                email_in = c_c2.text_input("Email Address")
                res_in = st.text_input("Residential Area")

                # SECTION 3: NEXT OF KIN
                st.caption("Next of Kin")
                c_d1, c_d2 = st.columns(2)
                nok_name = c_d1.text_input("NOK Name")
                nok_phone = c_d2.text_input("NOK Phone")

                # SECTION 4: SYSTEM
                st.caption("System")
                sponsor_in = st.text_input("Sponsor Name (Introduced By)")
                
                submitted = st.form_submit_button("Add Member", type="primary")
                
                if submitted:
                    if name_in and id_num_in:
                         # Convert DOB to string
                         dob_str = str(dob_in) if dob_in else ""
                         g_val = gender_in if gender_in != "Select..." else ""
                         
                         success = add_member(
                             group_id=gid, 
                             name=name_in, 
                             phone=phone_in, 
                             id_num=id_num_in,
                             email=email_in, 
                             residence=res_in, 
                             sponsor=sponsor_in,
                             kra_pin=kra_pin_in,
                             dob=dob_str,
                             gender=g_val,
                             occupation=occu_in,
                             next_of_kin_name=nok_name,
                             next_of_kin_phone=nok_phone
                         )
                         if success:
                             st.success(f"Added {name_in} successfully! (Auto-Account Generated)")
                             st.rerun()
                         else:
                             st.error("Failed to add member. Check if Name or Account Number already exists.")
                    else:
                        st.error("Name and ID Number are required.")
                         
            st.divider()
            
            st.subheader("Remove Member")
            if full_members:
                del_name = st.selectbox("Select Member to Remove", [m['Name'] for m in full_members], key="del_sel_mem")
                del_id = next((m['ID'] for m in full_members if m['Name'] == del_name), None)
                
                if st.button("🗑️ Delete Selected Member", type="primary"):
                    # Guardrail
                    if check_if_guarantor(del_name):
                         st.error(f"❌ Cannot delete {del_name}. They are listed as a guarantor for an active loan.")
                    else:
                         delete_member(del_id)
                         st.success(f"✅ Removed {del_name} from the group.")
                         st.rerun()
            else:
                st.info("No members to delete.")

        # --- Tab 3: Unified Borrowing Portfolio ---
        with tab3:
            st.subheader("📂 Active Borrowing Portfolio")
            
            loans_df = get_active_loans(gid)
            if not loans_df.empty:
                # Format Data for Display
                display_data = []
                for _, row in loans_df.iterrows():
                     # Determine Form Status
                     has_img = row['Image'] is not None and len(str(row['Image'])) > 5
                     display_data.append({
                         'Date': row['Date'],
                         'Borrower': row['Borrower'],
                         'Loan Amount': row['Amount'] if row['Type'] == 'Loan' else 0,
                         'Advance Amount': row['Amount'] if row['Type'] == 'Advance' else 0,
                         'Guarantors': row['Guarantors'],
                         'Form Status': "✅ Uploaded" if has_img else "⏳ Pending"
                     })
                     
                st.dataframe(pd.DataFrame(display_data), use_container_width=True)
                
                st.divider()
                st.markdown("#### 📎 Loan Documentation")
                
                # Select Loan to Upload Doc
                loan_opts = {f"{r['Borrower']} - {r['Date']} (Total: {r['Amount']})": r['Transaction ID'] for _, r in loans_df.iterrows()}
                
                sel_loan_lbl = st.selectbox("Select Loan Transaction", list(loan_opts.keys()))
                sel_tid = loan_opts[sel_loan_lbl]
                
                # Get current image path
                curr_img = loans_df.loc[loans_df['Transaction ID'] == sel_tid, 'Image'].values[0]
                
                c_up, c_view = st.columns(2)
                
                with c_up:
                    up_file = st.file_uploader("Upload Scanned Loan Form", type=['png', 'jpg', 'jpeg', 'pdf'])
                    if up_file:
                        if st.button("Save Document"):
                            save_loan_image(up_file, sel_tid)
                            st.success("Document Saved!")
                            st.rerun()
                            
                with c_view:
                    if curr_img and os.path.exists(curr_img):
                        st.success("✅ Document on File")
                        st.image(curr_img, caption="Loan Form")
                    else:
                        st.warning("⚠️ No Document Uploaded")
            else:
                st.info("No active loans or advances found for this group.")

if not st.session_state.setup_complete:
    # Router Logic
    if st.session_state.viewing_global_stats:
        view_global_stats()
        st.stop()
        
    if st.session_state.viewing_admin:
        view_admin_panel()
        st.stop()

    # --- Top Bar ---
    t1, t2, t3 = st.columns([6, 1.5, 1.5])
    t1.title("🤝 Jirani")
    
    if t2.button("📊 Global Stats"):
        st.session_state.viewing_global_stats = True
        st.rerun()
        
    if t3.button("⚙️ Admin Panel"):
        st.session_state.viewing_admin = True
        st.rerun()
    
    st.divider()
    
    # --- Main Section (2 Cols) ---
    col_select, col_create = st.columns([1, 1], gap="large")
    
    # --- LEFT: Select Existing Group ---
    with col_select:
        st.subheader("📂 Select Existing Group")
        
        # Fetch Extended Group Data
        all_groups_data = get_all_groups_extended()
        
        if all_groups_data:
            # Format selection options
            options_map = {f"{g['name']} (📅 {g['meeting_date']})": g['id'] for g in all_groups_data}
            
        if all_groups_data:
            # Format selection options
            options_map = {f"{g['name']} (📅 {g['meeting_date']})": g['id'] for g in all_groups_data}
            
            # TIGHT LAYOUT: Side-by-Side (3:1)
            # Vertical alignment handled by Streamlit (usually aligns top).
            # We can use st.columns with vertical_alignment="bottom" if supported (unlikely in older versions)
            # But standard columns are fine.
            
            c1, c2 = st.columns([3, 1])
            
            # Selectbox in C1
            with c1:
                selected_option = st.selectbox("Choose a Group to Audit:", list(options_map.keys()), label_visibility="visible")
                selected_id = options_map[selected_option]
            
            # Button in C2 - "Open Selected Group"
            # To align visually with the input box (which has a label), we might need an empty label or gap.
            # But "bottom" alignment is best. If not available, we just render.
                # Button in C2 - "Open Selected Group"
                # To align visually with the input box (which has a label), we might need an empty label or gap.
                # But "bottom" alignment is best. If not available, we just render.
                with c2:
                    # Spacer for label height approximation if needed, or just render.
                    st.write("") # Spacer
                    st.write("") # Spacer
                    if st.button("📂 Open", type="primary", use_container_width=True):
                        g_name, members = load_group_data(selected_id)
                        st.session_state.group_name = g_name
                        st.session_state.group_id = selected_id
                        st.session_state.info_msg = f"✅ Loaded: {g_name}"
        
                        st.session_state.temp_group_id = selected_id
                        st.rerun()

            # --- NESTED SETUP BLOCK (Inside Left Column) ---
            if 'temp_group_id' in st.session_state:
                 # Load name
                 g_name, _ = load_group_data(st.session_state.temp_group_id)
                 
                 st.divider()
                 st.markdown(f"**🎯 Setup: {g_name}**")
                 
                 with st.form("audit_context_form"):
                    c1, c2 = st.columns(2)
                    sel_month = c1.selectbox("Month", months_list)
                    sel_year = c2.number_input("Year", 2020, 2030, 2025)
                    
                    start_btn = st.form_submit_button("🚀 Start Audit", type="primary", use_container_width=True)
                    
                    if start_btn:
                        # Finalize Setup
                        st.session_state.group_name = g_name
                        st.session_state.group_id = st.session_state.temp_group_id
                        st.session_state.audit_month = sel_month
                        st.session_state.audit_year = sel_year
                        
                        # Check for Previous Data (Carry Forward)
                        prev_data_df = get_previous_month_data(st.session_state.group_id, sel_month, sel_year)
                        
                        # Load Bank Balance BF
                        st.session_state.bank_balance_bf = get_previous_bank_balance(st.session_state.group_id, sel_month, sel_year)
                        
                        # Load members fresh
                        _, members_tuples = load_group_data(st.session_state.group_id)
                        # members_tuples is (id, name)
                        
                        empty_df = init_empty_dataframe(members_tuples)
                        
                        if prev_data_df is not None and not prev_data_df.empty:
                            st.session_state.audit_df = merge_carry_forward(empty_df, prev_data_df)
                            st.session_state.info_msg += f" 🔄 Carried forward data from previous month."
                        else:
                            st.session_state.audit_df = empty_df
                            st.session_state.info_msg += " (Fresh start / No previous history)."
                        
                        # Default to Attendance Check Mode
                        st.session_state.audit_stage = "attendance_check"
                        
                        st.session_state.setup_complete = True
                        del st.session_state.temp_group_id
                        st.rerun()

    # --- RIGHT: Create New Group ---
    with col_create:
        container = st.container(border=True)
        with container:
            st.subheader("➕ Create New Group")
            new_name = st.text_input("New Group Name", placeholder="e.g. Sunrise Chama")
            first_meeting = st.date_input("First Meeting Date")
            new_members_txt = st.text_area("Initial Members (comma separated)", placeholder="Alice, Bob, Charlie")
            
            if st.button("Create New Group", type="secondary", use_container_width=True):
                if new_name and new_members_txt:
                    m_list = [x.strip() for x in new_members_txt.split(",") if x.strip()]
                    gid = create_new_group(new_name, m_list, first_meeting)
                    if gid:
                        st.success(f"Group '{new_name}' created!")
                        
                        # Auto-Start Audit Workflow
                        st.session_state.group_id = gid
                        st.session_state.group_name = new_name
                        st.session_state.setup_complete = True
                        st.session_state.started_audit = True
                        
                        # Time Context
                        st.session_state.audit_month = datetime.now().strftime("%B")
                        st.session_state.audit_year = datetime.now().year
                        
                        # Initialize Data
                        _, mems = load_group_data(gid)
                        st.session_state.audit_df = init_empty_dataframe(mems)
                        
                        # Set Stage to Collection/Attendance
                        st.session_state.audit_stage = "collection"
                        
                        st.rerun() 
                    else:
                        st.error("Group name already exists.")
                else:
                    st.error("Please fill Name and Members.")


    # Stop rendering the rest until setup is done
    st.stop()

# --- MAIN APP ---
elif st.session_state.viewing_profile:
    # PROFILE PAGE (Editable)
    idx = st.session_state.current_member_index
    df = st.session_state.audit_df
    name = df.at[idx, 'Member Name']
    mid = int(df.at[idx, 'Member ID'])
    
    # Load current details from DB
    details = get_member_details(mid)
    
    col_back, col_title = st.columns([1, 5])
    col_back.button("⬅️ Back to Audit", on_click=lambda: st.session_state.update(viewing_profile=False))
    col_title.title(f"User Profile: {name}")
    
    st.divider()
    
    c_left, c_right = st.columns([1, 2], gap="large")
    
    with c_left:
        # Photo Logic
        curr_photo = details.get('photo_path')
        if curr_photo and os.path.exists(curr_photo):
            st.image(curr_photo, width=200, caption=name)
        else:
            st.image("https://www.w3schools.com/howto/img_avatar.png", width=200, caption="No Photo")
            
        st.subheader("Update Photo")
        uploaded = st.file_uploader("Upload new photo", type=['png', 'jpg', 'jpeg'])
    
    with c_right:
        st.subheader("Personal Details")
        
        with st.form("profile_form"):
            # Provide current values as defaults
            d_phone = details.get('phone') or ""
            d_id = details.get('id_number') or ""
            d_kin = details.get('next_of_kin') or ""
            acc_num = details.get('account_number')
            
            # If account number is missing (legacy data), generate one
            if not acc_num:
                 acc_num = "N/A (Legacy)"
            
            st.metric("Account Number", f"{acc_num}")
            
            new_phone = st.text_input("Phone Number", value=d_phone)
            new_id = st.text_input("ID Number", value=d_id)
            new_kin = st.text_input("Next of Kin", value=d_kin)
            
            st.write(f"**Member ID (System):** {mid}")
            st.write(f"**Joined:** {details.get('joined_date')}")
            
            submitted = st.form_submit_button("Save Changes", type="primary")
            
            if submitted:
                # Handle Photo
                final_photo_path = None
                if uploaded:
                    final_photo_path = save_uploaded_file(uploaded, mid)
                
                update_member_details(mid, new_phone, new_id, new_kin, final_photo_path)
                st.success("Profile Updated Successfully!")
                st.rerun()

else:
    # --- Main Audit Interface (Stage Router) ---
    
    if st.session_state.audit_stage == 'attendance_check':
        render_attendance_view(st.session_state.group_id, st.session_state.group_name)
    
    elif st.session_state.audit_stage == 'collection':
        render_collection_view(st.session_state.group_id)
        
    elif st.session_state.audit_stage == 'allocation':
        render_allocation_view(st.session_state.group_id)
        
    # --- Inter-Stage Navigation / Completion ---
    
    # Status Msg
    if st.session_state.info_msg:
        st.info(st.session_state.info_msg)
        
    # Navigation to Next Month (After Completion)
    if st.session_state.show_navigation:
        st.divider()
        nxt_idx = (months_list.index(st.session_state.audit_month) + 1) % 12
        nxt_month = months_list[nxt_idx]
        nxt_year = st.session_state.audit_year + 1 if nxt_idx == 0 else st.session_state.audit_year
        
        st.warning(f"Audit finalized. Ready to proceed to {nxt_month} {nxt_year}?")
        if st.button(f"➡️ Open {nxt_month} {nxt_year}", type="primary"):
            # Reset Stage
            st.session_state.audit_stage = "collection"
            st.session_state.audit_month = nxt_month
            st.session_state.audit_year = nxt_year
            
            # Re-run Carry Forward Logic
            prev_data = get_previous_month_data(st.session_state.group_id, nxt_month, nxt_year)
            g_name, members = load_group_data(st.session_state.group_id) # Need members for init
            empty_df = init_empty_dataframe(members)
            
            if prev_data is not None:
                st.session_state.audit_df = merge_carry_forward(empty_df, prev_data)
                st.session_state.info_msg = f"Opened {nxt_month}. Data carried forward."
            else:
                 st.session_state.audit_df = empty_df
                 st.session_state.info_msg = f"Opened {nxt_month}. No previous data found."
            
            st.session_state.show_navigation = False
            st.rerun()
