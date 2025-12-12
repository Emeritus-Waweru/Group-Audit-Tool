import streamlit as st
import pandas as pd
from fpdf import FPDF
import io

st.set_page_config(layout="wide", page_title="Groups Audit Tool")

# --- 0. CSS Refinements (Global Override at Top) ---
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

if 'viewing_profile' not in st.session_state:
    st.session_state.viewing_profile = False

if 'history_dialog_open' not in st.session_state:
    st.session_state.history_dialog_open = False

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
        'Member Name', 'Total Cash Today', 'Fines', 
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
    """Helper for carry forward logic - Used in 'Next Month' flow as well."""
    # Step A: Deep Copy
    new_df = old_df.copy(deep=True)
    
    # Step B: Map Columns: New BF = Old CF
    new_df['Savings BF'] = old_df['Savings CF'].values
    new_df['Loan BF'] = old_df['Loan CF'].values
    new_df['Advance BF'] = old_df['Advance CF'].values
    
    # Step C: Explicit Zeroing (Nuclear Option)
    cols_to_zero = ['Total Cash Today', 'Fines', 'Loan Principal', 'Advance Principal', 'Savings Today', 'Loan Interest', 'Advance Interest']
    new_df.loc[:, cols_to_zero] = 0
        
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
    cash_today = int(df.at[idx, 'Total Cash Today'])
    
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
    # Format key dynamically to include month/year to avoid stale states
    m = st.session_state.audit_month
    y = st.session_state.audit_year
    key = f"{col}_{idx}_{m}_{y}"
    
    val = st.session_state[key]
    st.session_state.audit_df.at[idx, col] = val

@st.dialog("Audit History")
def view_history_dialog():
    st.write("Select a past audit to view:")
    if st.session_state.history:
        for key in st.session_state.history.keys():
            try:
                parts = key.split('_')
                label = f"{parts[2]} {parts[1]}"
                if st.button(f"📜 {label}", key=f"dlg_{key}", use_container_width=True):
                    st.session_state.selected_history_key = key
                    st.rerun()
            except:
                st.write(key)
        
        if 'selected_history_key' in st.session_state:
            st.divider()
            key = st.session_state.selected_history_key
            st.subheader(f"Snapshot: {key}")
            df_hist = st.session_state.history[key]
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("No saved audits yet.")

# --- 3. Reporting Logic ---

def calculate_top_performers(df):
    """Calculates top performers for summary."""
    # Ensure numeric types
    df_c = df.copy()
    numeric_cols = df_c.select_dtypes(include=['number']).columns
    for c in numeric_cols:
        df_c[c] = pd.to_numeric(df_c[c], errors='coerce').fillna(0)
    
    # Top Saver: Highest Savings Today
    saver_idx = df_c['Savings Today'].idxmax()
    saver = (df_c.at[saver_idx, 'Member Name'], df_c.at[saver_idx, 'Savings Today'])
    
    # Top Repayer: Loan Principal + Interest + Advance Princ
    # NOTE: User asked for Loan Repayer (Principal + Interest). I'll stick to that strictly? 
    # User said "Top Loan Repayer: Member with the highest Loan Principal + Loan Interest."
    df_c['TotalRepaid'] = df_c['Loan Principal'] + df_c['Loan Interest']
    repayer_idx = df_c['TotalRepaid'].idxmax()
    repayer = (df_c.at[repayer_idx, 'Member Name'], df_c.at[repayer_idx, 'TotalRepaid'])
    
    # Highest Borrower: Highest Loan BF (or new loan if we had a column for it, but we don't really have "New Loan" inputs, just BF tracking)
    # User said "Highest New Loan (if applicable) or Loan BF". We'll use Loan BF for now as that represents total debt load? Or Loan CF?
    # Usually "Highest Borrower" implies current debt. Let's use Loan BF + Advance BF to show total exposure?
    # User said "Highest Loan (if applicable) or Loan BF". Let's stick to Loan BF.
    borrower_idx = df_c['Loan BF'].idxmax()
    borrower = (df_c.at[borrower_idx, 'Member Name'], df_c.at[borrower_idx, 'Loan BF'])
    
    return {'saver': saver, 'repayer': repayer, 'borrower': borrower}

class PDF(FPDF):
    def header(self):
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        # Title
        title = f"{st.session_state.group_name} - Audit Report"
        self.cell(0, 10, title, 0, 1, 'C')
        # Subtitle
        self.set_font('Arial', '', 12)
        subtitle = f"{st.session_state.audit_month} {st.session_state.audit_year}"
        self.cell(0, 10, subtitle, 0, 1, 'C')
        self.ln(5)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    def chapter_body(self, df):
        # Executive Summary
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Executive Summary', 0, 1)
        self.set_font('Arial', '', 10)
        
        # Totals
        total_cash = int(df['Total Cash Today'].sum())
        total_repaid = int(df['Loan Principal'].sum() + df['Loan Interest'].sum()) # Just Loans? or Adv too? Sticking to Repayer definition
        total_savings = int(df['Savings Today'].sum())
        
        self.cell(0, 8, f"Total Cash Collected: {total_cash}", 0, 1)
        self.cell(0, 8, f"Total Loans Repaid: {total_repaid}", 0, 1)
        self.cell(0, 8, f"Total New Savings: {total_savings}", 0, 1)
        self.ln(5)
        
        # Top Performers
        perfs = calculate_top_performers(df)
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, "Top Performers:", 0, 1)
        self.set_font('Arial', '', 10)
        
        self.cell(0, 8, f"Top Saver: {perfs['saver'][0]} ({perfs['saver'][1]})", 0, 1)
        self.cell(0, 8, f"Top Loan Repayer: {perfs['repayer'][0]} ({perfs['repayer'][1]})", 0, 1)
        self.cell(0, 8, f"Highest Borrower: {perfs['borrower'][0]} ({perfs['borrower'][1]})", 0, 1)
        self.ln(10)
        
        # Master Ledger Table
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Master Ledger', 0, 1)
        self.set_font('Arial', 'B', 7) # Small font for table
        
        # Headers
        # Selecting specific columns to fit
        display_cols = [
            'Member Name', 'Total Cash', 'Sav BF', 'Sav Today', 'Sav CF',
            'Adv BF', 'Adv Int', 'Adv Prin', 'Adv CF',
            'Ln BF', 'Ln Int', 'Ln Prin', 'Ln CF', 'Fines'
        ]
        
        # Widths
        w = [25, 15, 15, 15, 15, 15, 12, 12, 15, 15, 12, 12, 15, 10]
        
        # Mapping DF headers to short headers
        header_map = {
            'Member Name': 'Member Name', 'Total Cash': 'Total Cash Today', 
            'Sav BF': 'Savings BF', 'Sav Today': 'Savings Today', 'Sav CF': 'Savings CF',
            'Adv BF': 'Advance BF', 'Adv Int': 'Advance Interest', 'Adv Prin': 'Advance Principal', 'Adv CF': 'Advance CF',
            'Ln BF': 'Loan BF', 'Ln Int': 'Loan Interest', 'Ln Prin': 'Loan Principal', 'Ln CF': 'Loan CF',
            'Fines': 'Fines'
        }
        
        for i, col in enumerate(display_cols):
            self.cell(w[i], 7, col, 1, 0, 'C')
        self.ln()
        
        self.set_font('Arial', '', 7)
        for index, row in df.iterrows():
            for i, col in enumerate(display_cols):
                real_col = header_map[col]
                val = str(int(row[real_col])) if isinstance(row[real_col], (int, float)) else str(row[real_col])
                self.cell(w[i], 6, val, 1, 0, 'C')
            self.ln()

def generate_pdf_report():
    pdf = PDF(orientation='L', format='A4') # Landscape
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.chapter_body(st.session_state.audit_df)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. UI Logic ---

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
                
                prev_month, prev_year = get_previous_period(sel_month, sel_year)
                prev_key = f"{g_name}_{prev_year}_{prev_month}"
                
                # --- ZEROING LOGIC START ---
                if prev_key in st.session_state.history:
                    # SCENARIO A: CARRY FORWARD
                    old_df = st.session_state.history[prev_key]
                    
                    # Step A: Deep Copy
                    new_df = old_df.copy(deep=True)
                    
                    # Step B: Map Balances
                    new_df['Savings BF'] = old_df['Savings CF'].values
                    new_df['Loan BF'] = old_df['Loan CF'].values
                    new_df['Advance BF'] = old_df['Advance CF'].values
                    
                    # Step C: Nuclear Zeroing
                    cols_to_zero = ['Total Cash Today', 'Fines', 'Loan Principal', 'Advance Principal', 'Savings Today', 'Loan Interest', 'Advance Interest']
                    new_df.loc[:, cols_to_zero] = 0
                    
                    st.session_state.audit_df = new_df
                    st.session_state.info_msg = f"🔄 Data carried forward from {prev_month} {prev_year}."
                
                else:
                    # SCENARIO B: FRESH START
                    if m_names:
                        members = [x.strip() for x in m_names.replace('\n', ',').split(',') if x.strip()]
                        st.session_state.audit_df = init_dataframe(members)
                        st.session_state.info_msg = "🆕 Starting fresh month (No previous history found)."
                    else:
                        st.error("Please provide Member Names for a fresh start.")
                        st.stop()
                
                # --- ZEROING LOGIC END ---
                
                st.session_state.setup_complete = True
                st.session_state.show_navigation = False # Ensure reset
                st.rerun()
            else:
                st.error("Please provide Group Name.")

elif st.session_state.viewing_profile:
    # PROFILE PAGE
    df = st.session_state.audit_df
    idx = st.session_state.current_member_index
    current_name = df.at[idx, 'Member Name']
    
    st.button("⬅️ Back to Audit", on_click=lambda: st.session_state.update(viewing_profile=False))
    st.title(f"📄 Member Profile: {current_name}")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.image("https://www.w3schools.com/howto/img_avatar.png", width=150)
    with c2:
        st.subheader("Personal Details")
        st.write(f"**Member ID:** {1000 + idx}")
        st.write(f"**Date Joined:** 01/01/2024")
        st.write(f"**Date of Birth:** 01/01/1980")
        st.write(f"**ID Number:** 12345678")
        st.write(f"**Next of Kin:** Spouse Name")
        st.write(f"**Phone:** +254 700 000 000")
        
    st.divider()
    st.subheader("📊 Performance & Attendance")
    st.info("No historical records available yet.")

else:
    # AUDIT PAGE (SPLIT SCREEN)
    
    # --- Top Bar ---
    c_head, c_actions = st.columns([1.5, 2.5])
    with c_head:
         st.header(f"{st.session_state.group_name} | {st.session_state.audit_month} {st.session_state.audit_year}")
    with c_actions:
        # Action Buttons Layout
        c_act1, c_act2, c_act3, c_act4 = st.columns([1.2, 1.2, 1.2, 0.8])
        
        with c_act1:
            if st.button("📂 History", use_container_width=True):
                view_history_dialog()

        with c_act2:
            # Download Report Button
            if st.session_state.setup_complete:
                pdf_bytes = generate_pdf_report()
                fname = f"Audit_Report_{st.session_state.group_name}_{st.session_state.audit_month}.pdf"
                st.download_button(
                    label="📄 Report",
                    data=pdf_bytes,
                    file_name=fname,
                    mime='application/pdf',
                    use_container_width=True
                )
                
        with c_act3:
            if not st.session_state.show_navigation:
                if st.button("💾 Finalize", type="primary", use_container_width=True):
                    key = f"{st.session_state.group_name}_{st.session_state.audit_year}_{st.session_state.audit_month}"
                    st.session_state.history[key] = st.session_state.audit_df.copy()
                    st.session_state.show_navigation = True
                    st.rerun()
                    
        with c_act4:
             if st.button("🏠 Exit", use_container_width=True):
                st.session_state.setup_complete = False
                st.session_state.show_navigation = False
                st.session_state.info_msg = ""
                st.rerun()

    if st.session_state.info_msg and not st.session_state.show_navigation:
        st.info(st.session_state.info_msg)

    # Navigation Logic (After Finalize)
    if st.session_state.show_navigation:
        st.success("✅ Audit Saved! Proceed to next month?")
        next_month, next_year = get_next_period(st.session_state.audit_month, st.session_state.audit_year)
        if st.button(f"➡️ Proceed to {next_month} {next_year}"):
            current_df = st.session_state.audit_df
            new_df = create_carry_forward_df(current_df)
            st.session_state.audit_df = new_df
            st.session_state.audit_month = next_month
            st.session_state.audit_year = next_year
            st.session_state.info_msg = f"🔄 Data carried forward to {next_month} {next_year}."
            st.session_state.show_navigation = False
            st.rerun()
        st.divider()

    left_col, right_col = st.columns([1, 2])
    
    # --- LEFT COL: Input Card ---
    with left_col:
        df = st.session_state.audit_df
        idx = st.session_state.current_member_index
        
        if len(df) > 0 and idx >= len(df):
            st.session_state.current_member_index = 0
            idx = 0
            st.rerun()
            
        current_name = df.at[idx, 'Member Name']
        
        with st.container(border=True):
            # Carousel
            c1, c2, c3 = st.columns([1, 4, 1])
            with c1:
                if st.button("⬅️", disabled=(idx == 0)):
                    st.session_state.current_member_index -= 1
                    st.rerun()
            with c2:
                st.image("https://www.w3schools.com/howto/img_avatar.png", width=80)
                st.subheader(current_name)
            with c3:
                if st.button("➡️", disabled=(idx == len(df)-1)):
                    st.session_state.current_member_index += 1
                    st.rerun()
            
            if st.button("📄 View Full Profile", use_container_width=True):
                st.session_state.viewing_profile = True
                st.rerun()
            
            st.divider()
            
            # Inputs
            input_cols = [
                'Total Cash Today', 
                'Fines', 
                'Savings BF', 
                'Loan BF', 
                'Loan Principal',
                'Advance BF', 
                'Advance Principal'
            ]
            
            for col in input_cols:
                val = df.at[idx, col]
                
                # Dynamic Key Logic to force reset when month changes
                w_key = f"{col}_{idx}_{st.session_state.audit_month}_{st.session_state.audit_year}"
                
                st.number_input(
                    col, 
                    value=int(val), 
                    step=1,
                    format="%d",
                    key=w_key,
                    on_change=update_val,
                    args=(col,)
                )
            
            st.write("")
            if st.button("💾 Save & Calculate", type="primary", use_container_width=True):
                calculate_waterfall(idx)
                st.success(f"Updated!")

    # --- RIGHT COL: Master Ledger ---
    with right_col:
        st.subheader(f"Master Ledger")
        
        disp_cols = [
            'Member Name', 'Total Cash Today', 
            'Savings BF', 'Savings Today', 'Savings CF', 
            'Advance BF', 'Advance Interest', 'Advance Principal', 'Advance CF', 
            'Loan BF', 'Loan Interest', 'Loan Principal', 'Loan CF', 
            'Fines'
        ]
        
        # Display Logic
        display_df = st.session_state.audit_df.copy()
        
        if len(display_df) > 0:
            # Totals
            numeric_cols = display_df.select_dtypes(include=['number']).columns
            totals = display_df[numeric_cols].sum()
            
            total_row = pd.DataFrame(columns=display_df.columns)
            total_row.loc[0, 'Member Name'] = 'TOTALS'
            for col in numeric_cols:
                total_row.loc[0, col] = totals[col]
            
            total_row = total_row.fillna("")
            display_df = pd.concat([display_df[disp_cols], total_row[disp_cols]], ignore_index=True)
        
        # Styling Function
        def highlight_logic(row):
            styles = [''] * len(row)
            if row['Member Name'] == 'TOTALS':
                return ['background-color: #262730; font-weight: bold; color: white'] * len(row)
            if row.name == idx:
                return ['background-color: #444444; color: white'] * len(row)
            return styles
            
        st.dataframe(
            display_df.style.apply(highlight_logic, axis=1).format(precision=0),
            use_container_width=True,
            hide_index=True
        )
