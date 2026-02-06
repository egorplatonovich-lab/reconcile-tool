import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile", layout="wide", page_icon="🧩")

st.title("🧩 Universal Reconciliation Tool")
st.markdown("Select an **Anchor Column** to link files, then choose which fields to compare.")
st.divider()

# --- HELPER FUNCTIONS ---
@st.cache_data
def load_data(file):
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
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
    """Clean Anchor Key (strip spaces, to string, lower case for better matching)"""
    return series.astype(str).fillna("").str.strip()

def clean_compare_string(series):
    """Clean Comparison Fields (strip, lower case)"""
    return series.astype(str).fillna("").str.strip()

# --- 1. UPLOAD ---
c1, c2 = st.columns(2)
with c1:
    f1 = st.file_uploader("📂 File 1 (Source)", key="f1")
with c2:
    f2 = st.file_uploader("📂 File 2 (Target)", key="f2")

# --- 2. CONFIGURATION ---
if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)

    if df1 is not None and df2 is not None:
        st.write("---")
        
        # === A. ANCHOR COLUMN (MANDATORY) ===
        st.subheader("🔗 1. Anchor Column (The Link)")
        st.info("Choose the column used to match rows (e.g., Transaction ID, Email, Username).")
        
        k1, k2 = st.columns(2)
        # Try to find common columns
        key_col_1 = k1.selectbox(f"Link Column ({f1.name})", df1.columns)
        key_col_2 = k2.selectbox(f"Link Column ({f2.name})", df2.columns)
        
        # Option to ignore missing keys
        report_missing = st.checkbox("📢 Report missing rows (Show 'Only in File 1' errors)", value=True, 
                                     help="Uncheck this if you only want to compare values for rows that exist in BOTH files.")

        # === B. COMPARISON MODULES ===
        st.subheader("⚙️ 2. What to compare?")
        
        col_conf1, col_conf2, col_conf3 = st.columns(3)

        # Module 1: Price
        with col_conf1:
            use_price = st.checkbox("💰 Price / Amount", value=True)
            p_col_1, p_col_2 = None, None
            if use_price:
                p_col_1 = st.selectbox(f"Price ({f1.name})", df1.columns, key="p1")
                p_col_2 = st.selectbox(f"Price ({f2.name})", df2.columns, key="p2")

        # Module 2: Variable A (e.g. User)
        with col_conf2:
            use_var_a = st.checkbox("String Field A (e.g. User)", value=False)
            va_col_1, va_col_2 = None, None
            if use_var_a:
                va_col_1 = st.selectbox(f"Field A ({f1.name})", df1.columns, key="va1")
                va_col_2 = st.selectbox(f"Field A ({f2.name})", df2.columns, key="va2")

        # Module 3: Variable B (e.g. Status)
        with col_conf3:
            use_var_b = st.checkbox("String Field B (e.g. Status)", value=False)
            vb_col_1, vb_col_2 = None, None
            if use_var_b:
                vb_col_1 = st.selectbox(f"Field B ({f1.name})", df1.columns, key="vb1")
                vb_col_2 = st.selectbox(f"Field B ({f2.name})", df2.columns, key="vb2")

        st.write("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # 1. Prepare Anchors
            df1['_anchor'] = clean_string_key(df1[key_col_1])
            df2['_anchor'] = clean_string_key(df2[key_col_2])

            # 2. Collect Columns
            cols_1 = [key_col_1, '_anchor']
            cols_2 = [key_col_2, '_anchor']

            # Prepare Data based on modules
            if use_price:
                df1['_clean_price'] = clean_currency(df1[p_col_1])
                df2['_clean_price'] = clean_currency(df2[p_col_2])
                cols_1 += [p_col_1, '_clean_price']
                cols_2 += [p_col_2, '_clean_price']

            if use_var_a:
                df1['_clean_va'] = clean_compare_string(df1[va_col_1])
                df2['_clean_va'] = clean_compare_string(df2[va_col_2])
                cols_1 += [va_col_1, '_clean_va']
                cols_2 += [va_col_2, '_clean_va']

            if use_var_b:
                df1['_clean_vb'] = clean_compare_string(df1[vb_col_1])
                df2['_clean_vb'] = clean_compare_string(df2[vb_col_2])
                cols_1 += [vb_col_1, '_clean_vb']
                cols_2 += [vb_col_2, '_clean_vb']

            # 3. MERGE
            merged = pd.merge(
                df1[list(set(cols_1))],
                df2[list(set(cols_2))],
                on='_anchor',
                how='outer',
                suffixes=('_1', '_2'),
                indicator=True
            )

            # 4. ERROR LOGIC
            def analyze_row(row):
                errors = []
                
                # Check Existence (Only if user wants to see missing rows)
                if report_missing:
                    if row['_merge'] == 'left_only': return ['Missing in File 2']
                    if row['_merge'] == 'right_only': return ['Missing in File 1']
                else:
                    # If we ignore missing, we skip rows that don't match
                    if row['_merge'] != 'both': return ['Ignore']

                # If row exists in both (or we are reporting missing and it is missing), check values
                if row['_merge'] == 'both':
                    # Check Price
                    if use_price:
                        p1 = float(row['_clean_price_1']) if pd.notnull(row['_clean_price_1']) else 0.0
                        p2 = float(row['_clean_price_2']) if pd.notnull(row['_clean_price_2']) else 0.0
                        if abs(p1 - p2) > 0.01: errors.append('Price Mismatch')
                    
                    # Check Var A
                    if use_var_a:
                        if str(row['_clean_va_1']) != str(row['_clean_va_2']): errors.append('Field A Mismatch')

                    # Check Var B
                    if use_var_b:
                        if str(row['_clean_vb_1']) != str(row['_clean_vb_2']): errors.append('Field B Mismatch')

                return errors if errors else ['OK']

            merged['Error_List'] = merged.apply(analyze_row, axis=1)
            
            # Filter out 'Ignore' status (rows that are missing but user unchecked "Report missing")
            merged = merged[merged['Error_List'].apply(lambda x: 'Ignore' not in x)]
            
            merged['Status'] = merged['Error_List'].apply(lambda x: ", ".join(x))
            discrepancies = merged[merged['Status'] != 'OK'].copy()

            # --- METRICS ---
            st.subheader("📊 Analysis Results")
            
            # Metric Columns (Dynamic)
            m_cols = st.columns(4)
            m_cols[0].metric("Total Matched Rows", len(merged))
            
            # Count specific errors
            missing_cnt = 0
            if report_missing:
                missing_cnt = len(discrepancies[discrepancies['Status'].str.contains('Missing')])
                m_cols[1].metric("Missing Rows", missing_cnt, delta_color="inverse")
            
            price_err = 0
            if use_price:
                price_err = discrepancies['Status'].str.contains('Price').sum()
                m_cols[2].metric("Price Mismatches", price_err, delta_color="inverse")
                
            other_err = 0
            if use_var_a or use_var_b:
                other_err = discrepancies['Status'].str.contains('Field').sum()
                m_cols[3].metric("Content Mismatches", other_err, delta_color="inverse")

            # --- TABLE DISPLAY ---
            if not discrepancies.empty:
                st.write("---")
                # Construct display columns
                disp = [key_col_1 + '_1']
                
                if use_price: 
                    merged['Diff'] = (merged['_clean_price_1'].fillna(0) - merged['_clean_price_2'].fillna(0)).round(2)
                    disp.extend([p_col_1 + '_1', p_col_2 + '_2', 'Diff'])
                
                if use_var_a: disp.extend([va_col_1 + '_1', va_col_2 + '_2'])
                if use_var_b: disp.extend([vb_col_1 + '_1', vb_col_2 + '_2'])
                
                disp.append('Status')

                # Rename for user friendliness
                final_df = discrepancies.rename(columns={key_col_1 + '_1': f"Anchor ({f1.name})"})
                final_disp = [f"Anchor ({f1.name})"] + disp[1:]

                # Coloring
                def color_rows(row):
                    s = row['Status']
                    css = 'color: black; '
                    if 'Missing' in s: return css + 'background-color: #ffcdd2' # Red
                    if 'Price' in s: return css + 'background-color: #fff9c4' # Yellow
                    if 'Field' in s: return css + 'background-color: #e1bee7' # Purple
                    return css

                st.dataframe(
                    final_df[final_disp].style.apply(lambda x: [color_rows(discrepancies.loc[x.name]) for i in x], axis=1),
                    use_container_width=True
                )
                
                # Download
                csv = final_df[final_disp].to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", csv, "report.csv", "text/csv", type="primary")

            else:
                st.balloons()
                st.success("✅ Clean! No discrepancies found based on your settings.")
