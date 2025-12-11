import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Groups Audit Tool")

# --- 0. CSS Refinements ---
st.markdown("""
<style>
    /* Reduce glare on dataframe selection and headers */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
    }
    .stDataFrame div[data-testid="stVerticalBlock"] {
        background-color: transparent;
    }
    /* Attempt to soften highlighting - note: specifics depend on theme but this helps contrast */
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)

# --- 1. State Management ---

if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False

if 'current_member_index' not in st.session_state:
    st.session_state.current_member_index = 0

if 'audit_df' not in st.session_state:
    st.session_state.audit_df = pd.DataFrame()

if 'group_name' not in st.session_state:
    st.session_state.group_name = ""

if 'audit_month' not in st.session_state:
    st.session_state.audit_month = ""

if 'audit_year' not in st.session_state:
    st.session_state.audit_year = 2025

if 'history' not in st.session_state:
    st.session_state.history = {}

if 'info_msg' not in st.session_state:
    st.session_state.info_msg = ""

if 'show_navigation' not in st.session_state:
    st.session_state.show_navigation = False

# --- 2. Helper Functions ---

months_list = ["January", "February", "March", "April", "May", "June", 
               "July", "August", "September", "October", "November", "December"]

def get_previous_period(month, year):
    """Calculates the previous month and year."""
    try:
        idx = months_list.index(month)
        if idx == 0:
            return "December", year - 1
        return months_list[idx - 1], year
    except ValueError:
        return None, None

def get_next_period(month, year):
    """Calculates the next month and year."""
    try:
        idx = months_list.index(month)
        if idx == 11: # December
            return "January", year + 1
        return months_list[idx + 1], year
    except ValueError:
        return None, None

def init_dataframe(member_list):
    """Initializes the dataframe with integer values."""
    cols = [
        'Member Name', 'Cash Today', 'Fines', 
        'Savings BF', 'Savings Today', 'Savings CF',
        'Loan BF', 'Loan Principal', 'Loan Interest', 'Loan CF',
        'Advance BF', 'Advance Principal', 'Advance Interest', 'Advance CF'
    ]
    df = pd.DataFrame(columns=cols)
    df['Member Name'] = member_list
    # Fill numeric cols with 0 (int)
    for c in cols[1:]:
        df[c] = 0
    return df

def create_carry_forward_df(old_df):
    """Creates a new DF based on the old one with Carry Forward logic."""
    members = old_df['Member Name'].tolist()
    new_df = init_dataframe(members)
    
    # Map Columns: New BF = Old CF
    new_df['Savings BF'] = old_df['Savings CF'].astype(int).values
    new_df['Loan BF'] = old_df['Loan CF'].astype(int).values
    new_df['Advance BF'] = old_df['Advance CF'].astype(int).values
    
    return new_df

def calculate_waterfall(idx):
    """Strict Integer Math Logic."""
    df = st.session_state.audit_df
    
    # Cast stored values to int
    adv_bf = int(df.at[idx, 'Advance BF'])
    loan_bf = int(df.at[idx, 'Loan BF'])
    fines = int(df.at[idx, 'Fines'])
    loan_prin = int(df.at[idx, 'Loan Principal'])
    adv_prin = int(df.at[idx, 'Advance Principal'])
    cash_today = int(df.at[idx, 'Cash Today'])
    
    # Step A: Advance Interest (10%)
    adv_int = int(adv_bf * 0.10)
    df.at[idx, 'Advance Interest'] = adv_int
    
    # Step B: Loan Interest (1.5%)
    loan_int = int(loan_bf * 0.015)
    df.at[idx, 'Loan Interest'] = loan_int
    
    # Step C: Total Deductions
    deductions = fines + loan_prin + loan_int + adv_prin + adv_int
    
    # Step D: Savings Today
    savings_today = cash_today - deductions
    df.at[idx, 'Savings Today'] = savings_today
    
    # Step E: Closing Figures
    sav_bf = int(df.at[idx, 'Savings BF'])
    df.at[idx, 'Savings CF'] = sav_bf + savings_today
    
    df.at[idx, 'Loan CF'] = loan_bf - loan_prin
    df.at[idx, 'Advance CF'] = adv_bf - adv_prin
    
    st.session_state.audit_df = df

def update_val(col):
    """Callback to update session state DF immediately on input change."""
    idx = st.session_state.current_member_index
    val = st.session_state[f"{col}_{idx}"]
    st.session_state.audit_df.at[idx, col] = val

# --- 3. UI Logic ---

if not st.session_state.setup_complete:
    # LANDING PAGE
    st.title("🛡️ Start Audit Session")
    
    with st.form("setup_form"):
        st.subheader("1. Group Configuration")
        g_name = st.text_input("Group Name", placeholder="e.g. Sunrise Chama")
        m_names = st.text_area("Member Names (comma separated)", placeholder="Alice, Bob, Charlie")
        
        st.divider()
        st.subheader("2. Audit Context")
        
        c1, c2 = st.columns(2)
        with c1:
            sel_month = st.selectbox("Select Month", months_list)
        with c2:
            sel_year = st.number_input("Select Year", min_value=2020, max_value=2030, value=2025, step=1)
            
        st.write("")
        submitted = st.form_submit_button("Start Audit", type="primary")
        
        if submitted:
            if g_name:
                st.session_state.group_name = g_name
                st.session_state.audit_month = sel_month
                st.session_state.audit_year = sel_year
                
                # Check for history
                prev_month, prev_year = get_previous_period(sel_month, sel_year)
                prev_key = f"{g_name}_{prev_year}_{prev_month}"
                
                if prev_key in st.session_state.history:
                    # SCENARIO A: CARRY FORWARD
                    old_df = st.session_state.history[prev_key]
                    st.session_state.audit_df = create_carry_forward_df(old_df)
                    st.session_state.info_msg = f"🔄 Data carried forward from {prev_month} {prev_year}."
                    st.session_state.setup_complete = True
                    st.session_state.show_navigation = False # Ensure reset
                    st.rerun()
                    
                else:
                    # SCENARIO B: FRESH START
                    if m_names:
                        members = [x.strip() for x in m_names.replace('\n', ',').split(',') if x.strip()]
                        st.session_state.audit_df = init_dataframe(members)
                        st.session_state.info_msg = "🆕 Starting fresh month (No previous history found)."
                        st.session_state.setup_complete = True
                        st.session_state.show_navigation = False # Ensure reset
                        st.rerun()
                    else:
                        st.error("Please provide Member Names for a fresh start.")
            else:
                st.error("Please provide Group Name.")

else:
    # AUDIT PAGE (SPLIT SCREEN)
    
    # Navigation Logic (After Finalize)
    if st.session_state.show_navigation:
        st.success("✅ Audit Saved! What would you like to do next?")
        
        next_month, next_year = get_next_period(st.session_state.audit_month, st.session_state.audit_year)
        
        col_next, col_exit = st.columns(2)
        
        with col_next:
            if st.button(f"➡️ Proceed to {next_month} {next_year}", type="primary", use_container_width=True):
                current_df = st.session_state.audit_df
                new_df = create_carry_forward_df(current_df)
                
                st.session_state.audit_df = new_df
                st.session_state.audit_month = next_month
                st.session_state.audit_year = next_year
                st.session_state.info_msg = f"🔄 Data carried forward to {next_month} {next_year}."
                st.session_state.show_navigation = False
                st.rerun()
                
        with col_exit:
            if st.button("🏠 Exit Group", use_container_width=True):
                st.session_state.setup_complete = False
                st.session_state.show_navigation = False
                st.session_state.info_msg = ""
                st.rerun()
        
        st.divider()

    # Sidebar: Finalize Button
    with st.sidebar:
        st.header("Actions")
        if not st.session_state.show_navigation:
            if st.button("💾 Finalize & Save Month", type="primary"):
                key = f"{st.session_state.group_name}_{st.session_state.audit_year}_{st.session_state.audit_month}"
                st.session_state.history[key] = st.session_state.audit_df.copy()
                st.session_state.show_navigation = True
                st.rerun()

    # Header
    header_text = f"Auditing: {st.session_state.group_name} | Period: {st.session_state.audit_month} {st.session_state.audit_year}"
    st.header(header_text)
    
    if st.session_state.info_msg and not st.session_state.show_navigation:
        st.info(st.session_state.info_msg)
    
    left_col, right_col = st.columns([1, 2])
    
    # --- LEFT COL: Input Card ---
    with left_col:
        df = st.session_state.audit_df
        idx = st.session_state.current_member_index
        
        # Safety check for index
        if len(df) > 0 and idx >= len(df):
            st.session_state.current_member_index = 0
            idx = 0
            st.rerun()
            
        current_name = df.at[idx, 'Member Name']
        
        # Carousel
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1:
            if st.button("⬅️", disabled=(idx == 0)):
                st.session_state.current_member_index -= 1
                st.rerun()
        with c2:
            st.subheader(current_name)
        with c3:
            if st.button("➡️", disabled=(idx == len(df)-1)):
                st.session_state.current_member_index += 1
                st.rerun()
        
        st.divider()
        
        # Inputs
        input_cols = [
            'Cash Today', 
            'Fines', 
            'Savings BF', 
            'Loan BF', 
            'Loan Principal',
            'Advance BF', 
            'Advance Principal'
        ]
        
        for col in input_cols:
            val = df.at[idx, col]
            st.number_input(
                col, 
                value=int(val), 
                step=1,
                format="%d",
                key=f"{col}_{idx}",
                on_change=update_val,
                args=(col,)
            )
            
        st.write("")
        if st.button("💾 Save & Calculate", use_container_width=True):
            calculate_waterfall(idx)
            st.success(f"Calculations updated for {current_name}!")

    # --- RIGHT COL: Master Ledger ---
    with right_col:
        st.subheader(f"Master Ledger")
        
        disp_cols = [
            'Member Name', 'Cash Today', 
            'Savings BF', 'Savings Today', 'Savings CF', 
            'Advance BF', 'Advance Interest', 'Advance Principal', 'Advance CF', 
            'Loan BF', 'Loan Interest', 'Loan Principal', 'Loan CF', 
            'Fines'
        ]
        
        # Generate Display Copy with Totals
        display_df = st.session_state.audit_df.copy()
        
        if len(display_df) > 0:
            # Calculate Totals
            numeric_cols = display_df.select_dtypes(include=['number']).columns
            totals = display_df[numeric_cols].sum()
            
            # Append Total Row
            total_row = pd.DataFrame(columns=display_df.columns)
            total_row.loc[0, 'Member Name'] = 'TOTALS'
            for col in numeric_cols:
                total_row.loc[0, col] = totals[col]
            
            # Fill safe NaN if any non-numeric columns exist (though not expected here)
            total_row = total_row.fillna("")
            
            display_df = pd.concat([display_df[disp_cols], total_row[disp_cols]], ignore_index=True)
        
        def highlight_row(row):
            if row['Member Name'] == 'TOTALS':
                 return ['font-weight: bold; background-color: #dbeafe'] * len(row)
            if row.name == idx:
                return ['background-color: #f0f2f6'] * len(row)
            return [''] * len(row)
            
        st.dataframe(
            display_df.style.apply(highlight_row, axis=1).format(precision=0),
            use_container_width=True,
            hide_index=True
        )
