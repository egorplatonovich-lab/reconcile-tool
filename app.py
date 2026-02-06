import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v7", layout="wide", page_icon="🧩")

# --- SESSION STATE INITIALIZATION ---
if 'analysis_done' not in st.session_state:
    st.session_state['analysis_done'] = False
if 'merged_data' not in st.session_state:
    st.session_state['merged_data'] = None
if 'discrepancies_data' not in st.session_state:
    st.session_state['discrepancies_data'] = None

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
    """Clean Anchor Key"""
    return series.astype(str).fillna("").str.strip()

def clean_compare_string(series):
    """Clean Comparison Fields"""
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
        
        # === A. ANCHOR COLUMN ===
        st.subheader("🔗 1. Anchor Column (The Link)")
        k1, k2 = st.columns(2)
        key_col_1 = k1.selectbox(f"Link Column ({f1.name})", df1.columns)
        key_col_2 = k2.selectbox(f"Link Column ({f2.name})", df2.columns)
        
        report_missing = st.checkbox("📢 Show unmatched rows (Show items missing in File 1 OR File 2)", value=True)

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

        # Module 2: Variable A
        with col_conf2:
            use_var_a = st.checkbox("String Field A (e.g. User)", value=False)
            va_col_1, va_col_2 = None, None
            if use_var_a:
                va_col_1 = st.selectbox(f"Field A ({f1.name})", df1.columns, key="va1")
                va_col_2 = st.selectbox(f"Field A ({f2.name})", df2.columns, key="va2")

        # Module 3: Variable B
        with col_conf3:
            use_var_b = st.checkbox("String Field B (e.g. Status)", value=False)
            vb_col_1, vb_col_2 = None, None
            if use_var_b:
                vb_col_1 = st.selectbox(f"Field B ({f1.name})", df1.columns, key="vb1")
                vb_col_2 = st.selectbox(f"Field B ({f2.name})", df2.columns, key="vb2")

        st.write("---")

        # --- RUN ANALYSIS ---
        # Кнопка теперь только ЗАПУСКАЕТ расчет и сохраняет в память
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

            # Calculate Diff immediately
            if use_price:
                merged['Diff'] = (merged['Price_1'].fillna(0) - merged['Price_2'].fillna(0)).round(2)

            # 4. ERROR LOGIC
            def analyze_row(row):
                errors = []
                
                # Check Existence
                if report_missing:
                    if row['_merge'] == 'left_only': return ['Missing in File 2']
                    if row['_merge'] == 'right_only': return ['Missing in File 1']
                else:
                    if row['_merge'] != 'both': return ['Ignore']

                # Check Values (only if exists in both)
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
            
            # Filter Ignore
            merged = merged[merged['Error_List'].apply(lambda x: 'Ignore' not in x)]
            
            # Create Status and Flag
            merged['Status'] = merged['Error_List'].apply(lambda x: ", ".join(x))
            merged['Flag'] = merged['Status'].apply(lambda x: '🟢' if x == 'OK' else '🔴')

            # Create discrepancies view
            discrepancies = merged[merged['Status'] != 'OK'].copy()
            
            # СОХРАНЯЕМ В ПАМЯТЬ (Session State)
            st.session_state['merged_data'] = merged
            st.session_state['discrepancies_data'] = discrepancies
            st.session_state['analysis_done'] = True

        # --- DISPLAY RESULTS (Берем из памяти, если анализ был сделан) ---
        if st.session_state['analysis_done']:
            
            # Восстанавливаем данные из памяти
            merged = st.session_state['merged_data']
            discrepancies = st.session_state['discrepancies_data']
            
            # --- METRICS ---
            st.subheader("📊 Analysis Results")
            
            m_cols = st.columns(4)
            m_cols[0].metric("Total Matched Rows", len(merged))
            
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

            # --- DISPLAY CONTROLS ---
            st.write("---")
            # Теперь эта галочка безопасна, так как данные берутся из st.session_state
            show_all = st.checkbox("Show all rows (including Matched)", value=False)
            
            # Decide which DataFrame to show
            if show_all:
                final_df_raw = merged.copy()
            else:
                final_df_raw = discrepancies.copy()

            # --- TABLE DISPLAY ---
            if not final_df_raw.empty:
                
                # Sort: Errors first
                final_df_raw = final_df_raw.sort_values(by=['Status'], ascending=False)

                # --- PREPARE COLUMNS ---
                cols_to_show = ['Flag', 'Anchor_Disp_1', 'Anchor_Disp_2']
                
                rename_map = {
                    'Anchor_Disp_1': f"{key_col_1} (File 1)",
                    'Anchor_Disp_2': f"{key_col_2} (File 2)"
                }
                
                if use_price: 
                    cols_to_show.extend(['Price_1', 'Price_2', 'Diff'])
                
                if use_var_a: cols_to_show.extend(['VarA_1', 'VarA_2'])
                if use_var_b: cols_to_show.extend(['VarB_1', 'VarB_2'])
                
                cols_to_show.append('Status')
                
                # Create final view
                final_df = final_df_raw[cols_to_show].rename(columns=rename_map)

                # Fill NaNs with "None"
                final_df = final_df.fillna("None")

                # --- STYLING LOGIC ---
                def style_table(val):
                    if str(val) == "None":
                        return 'color: #ff2b2b; font-weight: bold;' 
                    return '' 

                # Apply Styler
                st.dataframe(
                    final_df.style.applymap(style_table),
                    use_container_width=True,
                    hide_index=True
                )
                
                csv = final_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", csv, "report.csv", "text/csv", type="primary")

            else:
                if not show_all and discrepancies.empty:
                     st.balloons()
                     st.success("✅ Perfect! No discrepancies found (Enable 'Show all rows' to see matches).")
                elif show_all and merged.empty:
                     st.warning("No data found after filtering.")
