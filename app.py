import streamlit as st
import pandas as pd
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Reconciliation Tool", layout="wide", page_icon="⚖️")

st.title("⚖️ Final Reconciliation Tool")
st.markdown("Upload two files, map the columns, and spot the differences.")
st.divider()

# --- HELPER FUNCTIONS ---
@st.cache_data
def load_data(file):
    """Safe load for CSV/Excel"""
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Error reading {file.name}: {e}")
        return None

def clean_currency(series):
    """Standardize money formats"""
    if pd.api.types.is_numeric_dtype(series):
        return series
    # Remove symbols, spaces, convert commas to dots
    return series.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.').astype(float)

def clean_id_string(series):
    """Normalize IDs (strip spaces, convert to string)"""
    return series.astype(str).str.strip()

# --- 1. UPLOAD SECTION ---
c1, c2 = st.columns(2)
with c1:
    f1 = st.file_uploader("📂 File 1 (e.g. Internal Logs)", key="f1")
with c2:
    f2 = st.file_uploader("📂 File 2 (e.g. Provider Logs)", key="f2")

# --- 2. CONFIGURATION & LOGIC ---
if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)

    if df1 is not None and df2 is not None:
        st.write("---")
        st.subheader("🔧 Column Mapping")
        
        row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
        
        # Select ID Columns
        with row1_col1:
            id_col_1 = st.selectbox(f"ID Column in {f1.name}", df1.columns, index=0)
        with row1_col2:
            id_col_2 = st.selectbox(f"ID Column in {f2.name}", df2.columns, index=0)

        # Auto-find 'amount' columns
        def find_amount_idx(cols):
            for i, c in enumerate(cols):
                if 'sum' in str(c).lower() or 'amount' in str(c).lower(): return i
            return 0

        # Select Amount Columns
        with row1_col3:
            amt_col_1 = st.selectbox(f"Amount in {f1.name}", df1.columns, index=find_amount_idx(df1.columns))
        with row1_col4:
            amt_col_2 = st.selectbox(f"Amount in {f2.name}", df2.columns, index=find_amount_idx(df2.columns))

        # --- RUN BUTTON ---
        if st.button("🚀 Compare Files", type="primary"):
            
            # A. PREPROCESSING
            # Create standard key columns for merging
            df1['_merge_key'] = clean_id_string(df1[id_col_1])
            df2['_merge_key'] = clean_id_string(df2[id_col_2])
            
            # Clean amounts
            df1['_clean_amt'] = clean_currency(df1[amt_col_1])
            df2['_clean_amt'] = clean_currency(df2[amt_col_2])

            # B. MERGING (Full Outer Join)
            # We keep the original IDs to show them in the final table
            merged = pd.merge(
                df1[[id_col_1, '_clean_amt', '_merge_key']],
                df2[[id_col_2, '_clean_amt', '_merge_key']],
                on='_merge_key',
                how='outer',
                suffixes=('_1', '_2'),
                indicator=True
            )

            # C. CALCULATIONS
            merged['Amount_1'] = merged['_clean_amt_1'].fillna(0)
            merged['Amount_2'] = merged['_clean_amt_2'].fillna(0)
            merged['Diff'] = (merged['Amount_1'] - merged['Amount_2']).round(2)

            # D. STATUS LOGIC (English)
            def get_status(row):
                if row['_merge'] == 'left_only': return 'Only in File 1'
                if row['_merge'] == 'right_only': return 'Only in File 2'
                if row['Diff'] != 0: return 'Amount Mismatch'
                return 'OK'

            merged['Status'] = merged.apply(get_status, axis=1)

            # E. PREPARE FINAL REPORT
            report = merged.copy()
            
            # Rename columns to be clear
            final_col_id1 = f"{id_col_1} (File 1)"
            final_col_id2 = f"{id_col_2} (File 2)"
            
            report.rename(columns={
                id_col_1: final_col_id1,
                id_col_2: final_col_id2
            }, inplace=True)

            # Filter only discrepancies
            discrepancies = report[report['Status'] != 'OK'].copy()
            
            # Define column order for display
            display_cols = [
                final_col_id1, 
                final_col_id2, 
                'Amount_1', 
                'Amount_2', 
                'Diff', 
                'Status'
            ]

            # --- 3. RESULTS ---
            st.divider()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Rows", len(report))
            k2.metric("Mismatches", len(discrepancies), delta_color="inverse")
            k3.metric("Net Difference", f"{discrepancies['Diff'].sum():,.2f}")

            if not discrepancies.empty:
                st.subheader("⚠️ Discrepancies Found")
                
                # Dynamic Coloring WITH BLACK TEXT
                def style_table(val):
                    # Added 'color: black' to ensure text is readable on light background
                    if val == 'Only in File 1': 
                        return 'background-color: #e3f2fd; color: black;' 
                    if val == 'Only in File 2': 
                        return 'background-color: #fff3e0; color: black;' 
                    if val == 'Amount Mismatch': 
                        return 'background-color: #ffebee; color: black;' 
                    return ''

                # Show table
                st.dataframe(
                    discrepancies[display_cols].style.applymap(style_table, subset=['Status']).format("{:.2f}", subset=['Amount_1', 'Amount_2', 'Diff']),
                    use_container_width=True
                )

                # Download
                csv_data = discrepancies[display_cols].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Report (CSV)",
                    data=csv_data,
                    file_name="reconciliation_result.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.balloons()
                st.success("Perfect Match! No discrepancies.")
