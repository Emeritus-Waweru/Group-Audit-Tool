# Savings Group Audit Tool - Phase 1

**Professional Financial Auditing for Savings Groups (Chamas)**

The **Savings Group Audit Tool** is a robust, Streamlit-based application designed to digitize and streamline the auditing process for savings groups. It replaces manual ledger entry with a secure, automated, and error-free digital workflow.

## 🚀 Key Features

This application includes specialized financial logic tailored for group dynamics:

*   **Waterfall Deduction Logic**: Automatically calculates **Net Savings** logic. It deducts Fines, Principal Repayments, and Interest from the daily cash contribution before crediting the Savings balance.
*   **Session State Persistence**: Built on a robust session architecture that maintains data integrity across month switches and UI interactions, preventing accidental data loss during active audits.
*   **Carry Forward Engine**: Features a "Nuclear" Month-End Reset protocol. It automatically imports Closing Figures (CF) from the previous month as Opening Figures (BF) for the new month while strictly resetting transaction columns (Cash, Fines, Repayments).
*   **Split-Screen Interface**: Designed for speed and accuracy. The Left Panel features a Member Carousel for focused data entry, while the Right Panel updates the **Master Ledger** in real-time.
*   **PDF Reporting**: Generates professional, landscape-oriented Audit Reports on demand. Reports include an Executive Summary, **Top Performer Analysis** (Top Saver, Highest Borrower), and the full Master Ledger.

## 🛠️ Installation Instructions

Prerequisites: Python 3.8+

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/CipherInnovations/Group-Audit-Tool.git
    cd Group-Audit-Tool
    ```

2.  **Install Dependencies**
    Ensure you have `pip` installed. Run the following command to install the required packages (`streamlit`, `pandas`, `fpdf`, `openpyxl`):
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application**
    Launch the local web server:
    ```bash
    streamlit run main.py
    ```

## 📋 Usage Guide

1.  **Setup Group**: Initialize the session by entering the **Group Name** and **Member Names**.
2.  **Select Period**: Choose the current **Month** and **Year** for the audit.
3.  **Enter Data**: Use the left-hand panel to navigate through members. Enter **Cash**, **Fines**, and **Principal Repayments**. The system auto-calculates Interest and Balance Fwd.
4.  **Save & Calculate**: Click `Save` to update the Master Ledger.
5.  **Finalize Month**: When auditing is complete, click `Finalize` to lock the month and save it to history.
6.  **Report**: Click `📄 Report` to download the comprehensive PDF audit report.
