import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v12", layout="wide", page_icon="🧩")

# --- SESSION STATE INITIALIZATION ---
if 'analysis_done' not in st.session_state:
    st.session_state['analysis_done'] = False
if 'merged_data' not in st.session_state:
    st.session_state['merged_data'] = None
if 'discrepancies_data' not in st.session_state:
    st.session_state['discrepancies_data'] = None

st.title("🧩 Universal Reconciliation Tool")
st.markdown("Select an **Anchor Column** (Unique ID) to link files.")
st.divider()

# --- HELPER FUNCTIONS ---
@st.cache_data
def load_data(file):
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file, low_memory=False)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Error reading {file.name}: {e}")
        return None

def clean_currency(series):
    """Clean money format"""
    if pd.api.types.is_numeric_dtype(series):
        return series
    return series.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.').astype(float)

def clean_string_key(series):
    """Clean Anchor Key"""
    return series.astype(str).fillna("").str.strip()

def clean_compare_string(series):
    """Clean Comparison Fields"""
    return series.astype(str).fillna("").str.strip()

# --- 1. UPLOAD (RENAMED TO OUR / PROVIDER) ---
c1, c2 = st.columns(2)
with c1:
    f1 = st.file_uploader("📂 OUR (Internal Data)", key="f1")
with c2:
    f2 = st.file_uploader("📂 PROVIDER (External Data)", key="f2")

# --- 2. CONFIGURATION ---
if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)

    if df1 is not None and df2 is not None:
        st.write("---")
        
        # === A. ANCHOR COLUMN ===
        st.subheader("🔗 1. Anchor Column (The Link)")
        st.info("⚠️ Ensure this column is unique (ID). Linking by 'Status' or 'Date' will cause massive data explosion.")
        
        k1, k2 = st.columns(2)
        key_col_1 = k1.selectbox(f"Link Column (OUR - {f1.name})", df1.columns)
        key_col_2 = k2.selectbox(f"Link Column (PROVIDER - {f2.name})", df2.columns)
        
        # Check for duplicates
        dupes1 = df1[key_col_1].duplicated().sum()
        dupes2 = df2[key_col_2].duplicated().sum()
        if dupes1 > 0 or dupes2 > 0:
             st.warning(f"⚠️ Potential Risk: Anchor columns contain duplicates (OUR: {dupes1}, PROVIDER: {dupes2}). This may result in millions of rows.")

        # --- HIDDEN SETTING: ALWAYS REPORT MISSING ROWS ---
        report_missing = True 

        # === B. COMPARISON MODULES ===
        st.subheader("⚙️ 2. What to compare?")
        
        col_conf1, col_conf2, col_conf3 = st.columns(3)

        # Module 1: Price
        with col_conf1:
            use_price = st.checkbox("💰 Price / Amount", value=True)
            p_col_1, p_col_2 = None, None
            if use_price:
                p_col_1 = st.selectbox(f"Price (OUR)", df1.columns, key="p1")
                p_col_2 = st.selectbox(f"Price (PROVIDER)", df2.columns, key="p2")

        # Module 2: Variable A
        with col_conf2:
            use_var_a = st.checkbox("String Field A (e.g. User)", value=False)
            va_col_1, va_col_2 = None, None
            if use_var_a:
                va_col_1 = st.selectbox(f"Field A (OUR)", df1.columns, key="va1")
                va_col_2 = st.selectbox(f"Field A (PROVIDER)", df2.columns, key="va2")

        # Module 3: Variable B
        with col_conf3:
            use_var_b = st.checkbox("String Field B (e.g. Status)", value=False)
            vb_col_1, vb_col_2 = None, None
            if use_var_b:
                vb_col_1 = st.selectbox(f"Field B (OUR)", df1.columns, key="vb1")
                vb_col_2 = st.selectbox(f"Field B (PROVIDER)", df2.columns, key="vb2")

        st.write("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # 1. Prepare Data
            data1 = pd.DataFrame()
            data2 = pd.DataFrame()

            # Anchors
            data1['_anchor'] = clean_string_key(df1[key_col_1])
            data2['_anchor'] = clean_string_key(df2[key_col_2])
            
            # Visible Anchors
            data1['Anchor_Disp_1'] = df1[key_col_1].astype(str)
            data2['Anchor_Disp_2'] = df2[key_col_2].astype(str)

            # Price
            if use_price:
                data1['Price_1'] = clean_currency(df1[p_col_1])
                data2['Price_2'] = clean_currency(df2[p_col_2])

            # Var A
            if use_var_a:
                data1['VarA_1'] = clean_compare_string(df1[va_col_1])
                data2['VarA_2'] = clean_compare_string(df2[va_col_2])
            
            # Var B
            if use_var_b:
                data1['VarB_1'] = clean_compare_string(df1[vb_col_1])
                data2['VarB_2'] = clean_compare_string(df2[vb_col_2])

            # 3. MERGE
            merged = pd.merge(
                data1,
                data2,
                on='_anchor',
                how='outer',
                indicator=True
            )

            # Calculate Diff (OUR - PROVIDER)
            if use_price:
                merged['Diff'] = (merged['Price_1'].fillna(0) - merged['Price_2'].fillna(0)).round(2)

            # 4. ERROR LOGIC
            def analyze_row(row):
                errors = []
                
                # Check Existence (Always ON now)
                if row['_merge'] == 'left_only': return ['Missing in PROVIDER']
                if row['_merge'] == 'right_only': return ['Missing in OUR']

                if row['_merge'] == 'both':
                    if use_price:
                        p1 = float(row['Price_1']) if pd.notnull(row['Price_1']) else 0.0
                        p2 = float(row['Price_2']) if pd.notnull(row['Price_2']) else 0.0
                        if abs(p1 - p2) > 0.01: errors.append('Price Mismatch')
                    
                    if use_var_a:
                        if str(row['VarA_1']) != str(row['VarA_2']): errors.append('Field A Mismatch')

                    if use_var_b:
                        if str(row['VarB_1']) != str(row['VarB_2']): errors.append('Field B Mismatch')

                return errors if errors else ['OK']

            merged['Error_List'] = merged.apply(analyze_row, axis=1)
            merged['Status'] = merged['Error_List'].apply(lambda x: ", ".join(x))

            # Create discrepancies view
            discrepancies = merged[merged['Status'] != 'OK'].copy()
            
            # STORE IN SESSION STATE
            st.session_state['merged_data'] = merged
            st.session_state['discrepancies_data'] = discrepancies
            st.session_state['analysis_done'] = True

        # --- DISPLAY RESULTS ---
        if st.session_state['analysis_done']:
            
            merged = st.session_state['merged_data']
            discrepancies = st.session_state['discrepancies_data']
            
            # --- METRICS ---
            st.subheader("📊 Analysis Results")
            
            m_cols = st.columns(4)
            m_cols[0].metric("Total Matched Rows", len(merged))
            
            # Missing Rows
            missing_cnt = len(discrepancies[discrepancies['Status'].str.contains('Missing')])
            m_cols[1].metric("Missing Rows", missing_cnt, delta_color="inverse")
            
            # Price Mismatches with SUM Diff
            price_err_count = 0
            price_diff_sum = 0.0
            
            if use_price:
                # Filter rows that specifically have a Price Mismatch (ignoring pure missing rows for this sum if needed, 
                # or including them if they have 0 vs Value. Logic: 'Price Mismatch' tag is only added for 'both' rows in analyze_row function)
                price_mismatch_rows = discrepancies[discrepancies['Status'].str.contains('Price Mismatch')]
                price_err_count = len(price_mismatch_rows)
                price_diff_sum = price_mismatch_rows['Diff'].sum()
                
                # Display Count as value, Sum as Delta
                m_cols[2].metric(
                    label="Price Mismatches", 
                    value=f"{price_err_count}", 
                    delta=f"{price_diff_sum:,.2f}", 
                    delta_color="normal" # Green for positive (Our > Prov), Red for negative (Our < Prov)
                )
                
            other_err = 0
            if use_var_a or use_var_b:
                other_err = discrepancies['Status'].str.contains('Field').sum()
                m_cols[3].metric("Content Mismatches", other_err, delta_color="inverse")

            # --- DISPLAY CONTROLS ---
            st.write("---")
            show_all = st.checkbox("Show all rows (including Matched)", value=False)
            
            if show_all:
                final_df_raw = merged.copy()
            else:
                final_df_raw = discrepancies.copy()

            # --- TABLE DISPLAY ---
            if not final_df_raw.empty:
                
                # Sort: Errors first
                final_df_raw = final_df_raw.sort_values(by=['Status'], ascending=False)

                # --- PREPARE COLUMNS ---
                cols_to_show = ['Anchor_Disp_1', 'Anchor_Disp_2']
                
                rename_map = {
                    'Anchor_Disp_1': f"{key_col_1} (OUR)",
                    'Anchor_Disp_2': f"{key_col_2} (PROVIDER)"
                }
                
                if use_price: 
                    cols_to_show.extend(['Price_1', 'Price_2', 'Diff'])
                
                if use_var_a: cols_to_show.extend(['VarA_1', 'VarA_2'])
                if use_var_b: cols_to_show.extend(['VarB_1', 'VarB_2'])
                
                cols_to_show.append('Status')
                
                # --- DOWNLOAD & DISPLAY PREP ---
                download_df = final_df_raw[cols_to_show].rename(columns=rename_map)
                csv = download_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full Report (CSV)", csv, "report.csv", "text/csv", type="primary")

                # LIMIT VISUALS
                MAX_ROWS_DISPLAY = 100000
                if len(final_df_raw) > MAX_ROWS_DISPLAY:
                    st.warning(f"⚠️ Display limit reached ({len(final_df_raw)} rows). Showing first 1000 rows. Use Download for full data.")
                    display_df = download_df.head(1000).fillna("None")
                else:
                    display_df = download_df.fillna("None")
                
                # Styling
                def color_none(val):
                    if str(val) == "None": return 'color: #d32f2f; font-weight: bold;' 
                    return ''
                
                def color_status(val):
                    if val == 'OK': return 'color: #2e7d32; font-weight: bold;'
                    else: return 'color: #d32f2f; font-weight: bold;'

                st.dataframe(
                    display_df.style.map(color_none).map(color_status, subset=['Status']),
                    use_container_width=True,
                    hide_index=True
                )

            else:
                if not show_all and discrepancies.empty:
                     st.balloons()
                     st.success("✅ Perfect! No discrepancies found.")
                elif show_all and merged.empty:
                     st.warning("No data found after filtering.")
