import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v16", layout="wide", page_icon="🧩")

# --- SESSION STATE INITIALIZATION ---
if 'analysis_done' not in st.session_state:
    st.session_state['analysis_done'] = False
if 'merged_data' not in st.session_state:
    st.session_state['merged_data'] = None
if 'discrepancies_data' not in st.session_state:
    st.session_state['discrepancies_data'] = None

st.title("🧩 Universal Reconciliation Tool")

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
    if pd.api.types.is_numeric_dtype(series):
        return series
    return series.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.').astype(float)

def clean_string_key(series):
    return series.astype(str).fillna("").str.strip()

def clean_compare_string(series):
    return series.astype(str).fillna("").str.strip()

# --- 1. UPLOAD ---
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
        st.markdown("---")
        
        # === A. ANCHOR COLUMN ===
        st.subheader("🔗 1. Anchor (Unique ID)")
        
        anchor_help_text = "⚠️ IMPORTANT: This column must be UNIQUE. Do NOT use dates or statuses here."
        
        k1, k2, k_buff = st.columns([2, 2, 3]) 
        with k1:
            key_col_1 = st.selectbox(f"Column in OUR", df1.columns, help=anchor_help_text)
        with k2:
            key_col_2 = st.selectbox(f"Column in PROVIDER", df2.columns, help=anchor_help_text)
        
        dupes1 = df1[key_col_1].duplicated().sum()
        dupes2 = df2[key_col_2].duplicated().sum()
        if dupes1 > 0 or dupes2 > 0:
             st.warning(f"⚠️ Risk: Duplicates found in anchor (OUR: {dupes1}, PROVIDER: {dupes2}). Results might be huge.")

        report_missing = True 

        # === B. COMPARISON MODULES ===
        st.write("")
        st.subheader("⚙️ 2. Comparison Fields")
        
        # --- ROW 1: PRICE ---
        use_price = st.checkbox("💰 Compare Price / Amount", value=True)
        p_col_1, p_col_2 = None, None
        
        if use_price:
            pc1, pc2, pc3 = st.columns([2, 2, 3]) 
            with pc1:
                p_col_1 = st.selectbox("Price (OUR)", df1.columns, key="p1")
            with pc2:
                p_col_2 = st.selectbox("Price (PROVIDER)", df2.columns, key="p2")
        
        st.write("") 

        # --- ROW 2: USER ---
        use_var_a = st.checkbox("👤 Compare User", value=False)
        va_col_1, va_col_2 = None, None
        
        if use_var_a:
            vc1, vc2, vc3 = st.columns([2, 2, 3])
            with vc1:
                va_col_1 = st.selectbox("User (OUR)", df1.columns, key="va1")
            with vc2:
                va_col_2 = st.selectbox("User (PROVIDER)", df2.columns, key="va2")

        st.write("") 

        # --- ROW 3: ADDITIONAL FIELD ---
        use_var_b = st.checkbox("🧩 Compare Additional Field", value=False)
        vb_col_1, vb_col_2 = None, None
        
        if use_var_b:
            vb1, vb2, vb3 = st.columns([2, 2, 3])
            with vb1:
                vb_col_1 = st.selectbox("Additional (OUR)", df1.columns, key="vb1")
            with vb2:
                vb_col_2 = st.selectbox("Additional (PROVIDER)", df2.columns, key="vb2")

        st.markdown("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # --- 0. VALIDATION CHECK (ЗАЩИТА ОТ ДУРАКА) ---
            # Проверяем, не выбрал ли юзер одну и ту же колонку для Якоря и Сравнения
            errors_found = []
            
            if use_var_a:
                if va_col_1 == key_col_1:
                    errors_found.append(f"❌ Error: You selected '{va_col_1}' as both ANCHOR and USER (OUR). This is redundant.")
                if va_col_2 == key_col_2:
                    errors_found.append(f"❌ Error: You selected '{va_col_2}' as both ANCHOR and USER (PROVIDER). This is redundant.")
            
            if use_var_b:
                if vb_col_1 == key_col_1:
                    errors_found.append(f"❌ Error: You selected '{vb_col_1}' as both ANCHOR and ADDITIONAL (OUR).")
                if vb_col_2 == key_col_2:
                    errors_found.append(f"❌ Error: You selected '{vb_col_2}' as both ANCHOR and ADDITIONAL (PROVIDER).")
            
            # Если нашли ошибки — останавливаемся и показываем их
            if errors_found:
                for err in errors_found:
                    st.error(err)
                st.stop() # Остановка выполнения, чтобы не упало с KeyError

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

            # Var A (User)
            if use_var_a:
                data1['User_1'] = clean_compare_string(df1[va_col_1])
                data2['User_2'] = clean_compare_string(df2[va_col_2])
            
            # Var B (Additional)
            if use_var_b:
                data1['Add_1'] = clean_compare_string(df1[vb_col_1])
                data2['Add_2'] = clean_compare_string(df2[vb_col_2])

            # 3. MERGE
            merged = pd.merge(
                data1,
                data2,
                on='_anchor',
                how='outer',
                indicator=True
            )

            # Calculate Diff
            if use_price:
                merged['Diff'] = (merged['Price_1'].fillna(0) - merged['Price_2'].fillna(0)).round(2)

            # 4. ERROR LOGIC
            def analyze_row(row):
                errors = []
                
                if row['_merge'] == 'left_only': return ['Missing in PROVIDER']
                if row['_merge'] == 'right_only': return ['Missing in OUR']

                if row['_merge'] == 'both':
                    if use_price:
                        p1 = float(row['Price_1']) if pd.notnull(row['Price_1']) else 0.0
                        p2 = float(row['Price_2']) if pd.notnull(row['Price_2']) else 0.0
                        if abs(p1 - p2) > 0.01: errors.append('Price Mismatch')
                    
                    if use_var_a:
                        if str(row['User_1']) != str(row['User_2']): errors.append('User Mismatch')

                    if use_var_b:
                        if str(row['Add_1']) != str(row['Add_2']): errors.append('Additional Field Mismatch')

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
            m_cols[0].metric("Total Matched", len(merged))
            
            # Missing Rows
            missing_cnt = len(discrepancies[discrepancies['Status'].str.contains('Missing')])
            m_cols[1].metric("Missing Rows", missing_cnt, delta_color="inverse")
            
            # Price Mismatches
            if use_price:
                price_mismatch_rows = discrepancies[discrepancies['Status'].str.contains('Price Mismatch')]
                price_err_count = len(price_mismatch_rows)
                price_diff_sum = price_mismatch_rows['Diff'].sum()
                
                m_cols[2].metric(
                    label="Price Mismatches", 
                    value=f"{price_err_count}", 
                    delta=f"{price_diff_sum:,.2f}", 
                    delta_color="normal"
                )
            else:
                m_cols[2].metric("Price Mismatches", "N/A")
                
            # Content Mismatches
            other_err = 0
            if use_var_a or use_var_b:
                if use_var_a: other_err += discrepancies['Status'].str.contains('User Mismatch').sum()
                if use_var_b: other_err += discrepancies['Status'].str.contains('Additional').sum()
                m_cols[3].metric("Content Mismatches", other_err, delta_color="inverse")
            else:
                 m_cols[3].metric("Content Mismatches", "N/A")

            # --- DISPLAY CONTROLS ---
            st.write("---")
            show_all = st.checkbox("Show all rows (including Matched)", value=False)
            
            if show_all:
                final_df_raw = merged.copy()
            else:
                final_df_raw = discrepancies.copy()

            # --- TABLE DISPLAY ---
            if not final_df_raw.empty:
                
                final_df_raw = final_df_raw.sort_values(by=['Status'], ascending=False)

                cols_to_show = ['Anchor_Disp_1', 'Anchor_Disp_2']
                # Возвращаем красивые названия колонок как в v14
                rename_map = {
                    'Anchor_Disp_1': f"{key_col_1} (OUR)",
                    'Anchor_Disp_2': f"{key_col_2} (PROV)"
                }
                
                if use_price: 
                    cols_to_show.extend(['Price_1', 'Price_2', 'Diff'])
                
                if use_var_a: 
                    # Тут мы используем имена колонок без префиксов, так как валидация выше не даст им совпасть с якорем
                    final_df_raw.rename(columns={'User_1': f"{va_col_1} (OUR)", 'User_2': f"{va_col_2} (PROV)"}, inplace=True)
                    cols_to_show.extend([f"{va_col_1} (OUR)", f"{va_col_2} (PROV)"])
                    
                if use_var_b: 
                    final_df_raw.rename(columns={'Add_1': f"{vb_col_1} (OUR)", 'Add_2': f"{vb_col_2} (PROV)"}, inplace=True)
                    cols_to_show.extend([f"{vb_col_1} (OUR)", f"{vb_col_2} (PROV)"])
                
                cols_to_show.append('Status')
                
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
