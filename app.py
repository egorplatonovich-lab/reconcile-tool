import streamlit as st
import pandas as pd
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v27", layout="wide", page_icon="🧩")

# --- SESSION STATE ---
if 'analysis_done' not in st.session_state: st.session_state['analysis_done'] = False
if 'main_df' not in st.session_state: st.session_state['main_df'] = None
if 'investigation_df' not in st.session_state: st.session_state['investigation_df'] = None

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
    if pd.api.types.is_numeric_dtype(series): return series
    return series.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.').astype(float)

def clean_string_key(series):
    s = series.astype(str).fillna("")
    s = s.str.strip().str.lower()
    s = s.str.replace(r'\.0$', '', regex=True)
    return s

def clean_compare_string(series):
    return series.astype(str).fillna("").str.strip()

def nuclear_date_parser(val):
    s = str(val).strip()
    s = s.replace('T', ' ').replace('Z', '')
    
    # ISO
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if iso_match:
        try: return pd.to_datetime(iso_match.group(1))
        except: pass
            
    # Euro
    euro_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', s)
    if euro_match:
        try: return pd.to_datetime(euro_match.group(1), dayfirst=True)
        except: pass

    try: return pd.to_datetime(s, errors='coerce')
    except: return pd.NaT

def find_date_col(cols):
    for c in cols:
        if 'date' in c.lower() or 'time' in c.lower() or 'created' in c.lower() or 'at' in c.lower():
            return c
    return cols[0]

# --- 1. UPLOAD ---
c1, c2 = st.columns(2)
with c1: f1 = st.file_uploader("📂 OUR (Internal Data)", key="f1")
with c2: f2 = st.file_uploader("📂 PROVIDER (External Data)", key="f2")

# --- 2. CONFIGURATION ---
if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)

    if df1 is not None and df2 is not None:
        st.markdown("---")
        
        # === A. DATE & ANCHOR ===
        st.subheader("🗓️ 1. Period & Anchor")
        
        col_per1, col_per2, col_per3, col_per4 = st.columns(4)
        with col_per1:
            target_year = st.selectbox("Target Year", range(2023, 2030), index=3)
        with col_per2:
            months = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 
                      7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
            target_month_name = st.selectbox("Target Month", list(months.values()))
            target_month = list(months.keys())[list(months.values()).index(target_month_name)]
        
        idx_d1 = list(df1.columns).index(find_date_col(df1.columns))
        idx_d2 = list(df2.columns).index(find_date_col(df2.columns))

        with col_per3: date_col_1 = st.selectbox("Date Column (OUR)", df1.columns, index=idx_d1)
        with col_per4: date_col_2 = st.selectbox("Date Column (PROVIDER)", df2.columns, index=idx_d2)

        st.write("")
        k1, k2 = st.columns(2)
        key_col_1 = k1.selectbox(f"Anchor ID (OUR)", df1.columns)
        key_col_2 = k2.selectbox(f"Anchor ID (PROVIDER)", df2.columns)
        
        if df1[key_col_1].duplicated().any() or df2[key_col_2].duplicated().any():
             st.warning(f"⚠️ Warning: Anchors contain duplicates.")

        # === B. COMPARISON FIELDS ===
        st.subheader("⚙️ 2. Comparison Fields")
        use_price = st.checkbox("💰 Compare Price", value=True)
        p_col_1, p_col_2 = None, None
        if use_price:
            pc1, pc2 = st.columns(2)
            p_col_1 = pc1.selectbox("Price (OUR)", df1.columns, key="p1")
            p_col_2 = pc2.selectbox("Price (PROVIDER)", df2.columns, key="p2")
        
        use_var_a = st.checkbox("👤 Compare User", value=False)
        va_col_1, va_col_2 = None, None
        if use_var_a:
            vc1, vc2 = st.columns(2)
            va_col_1 = vc1.selectbox("User (OUR)", df1.columns, key="va1")
            va_col_2 = vc2.selectbox("User (PROVIDER)", df2.columns, key="va2")

        use_var_b = st.checkbox("🧩 Compare Additional", value=False)
        vb_col_1, vb_col_2 = None, None
        if use_var_b:
            vb1, vb2 = st.columns(2)
            vb_col_1 = vb1.selectbox("Add'l (OUR)", df1.columns, key="vb1")
            vb_col_2 = vb2.selectbox("Add'l (PROVIDER)", df2.columns, key="vb2")

        st.markdown("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # 1. PARSE DATES
            df1['_date_obj'] = df1[date_col_1].apply(nuclear_date_parser)
            df2['_date_obj'] = df2[date_col_2].apply(nuclear_date_parser)
            
            if df1['_date_obj'].notna().sum() == 0:
                st.error(f"❌ Error: Dates not parsed in OUR file.")
                st.stop()
            if df2['_date_obj'].notna().sum() == 0:
                st.error(f"❌ Error: Dates not parsed in PROVIDER file.")
                st.stop()

            # 2. PREPARE DATA
            data1 = pd.DataFrame()
            data2 = pd.DataFrame()
            
            data1['_anchor'] = clean_string_key(df1[key_col_1])
            data2['_anchor'] = clean_string_key(df2[key_col_2])
            
            data1['ID_OUR'] = df1[key_col_1].astype(str)
            data2['ID_PROV'] = df2[key_col_2].astype(str)
            data1['Date_OUR'] = df1['_date_obj']
            data2['Date_PROV'] = df2['_date_obj']

            if use_price:
                data1['Price_1'] = clean_currency(df1[p_col_1])
                data2['Price_2'] = clean_currency(df2[p_col_2])
            if use_var_a:
                data1['User_1'] = clean_compare_string(df1[va_col_1])
                data2['User_2'] = clean_compare_string(df2[va_col_2])
            if use_var_b:
                data1['Add_1'] = clean_compare_string(df1[vb_col_1])
                data2['Add_2'] = clean_compare_string(df2[vb_col_2])

            # 3. GLOBAL MERGE
            full_merge = pd.merge(data1, data2, on='_anchor', how='outer', indicator=True)

            # 4. FILTERING
            def check_month(dt):
                if pd.isna(dt): return False
                return (dt.month == target_month) and (dt.year == target_year)

            full_merge['In_Month_OUR'] = full_merge['Date_OUR'].apply(check_month)
            full_merge['In_Month_PROV'] = full_merge['Date_PROV'].apply(check_month)

            main_mask = full_merge['In_Month_OUR'] | full_merge['In_Month_PROV']
            df_main = full_merge[main_mask].copy()

            # 5. ANALYZE MAIN (NEW LOGIC)
            if use_price:
                df_main['Diff'] = (df_main['Price_1'].fillna(0) - df_main['Price_2'].fillna(0)).round(2)

            def analyze_main(row):
                errs = []
                
                # Check Local Existence (in this month)
                loc_our = row['In_Month_OUR']
                loc_prov = row['In_Month_PROV']
                
                # Check Global Existence (Merge indicator: left_only, right_only, both)
                global_merge = row['_merge']

                # --- MISSING LOGIC UPDATED ---
                
                # Case 1: Active in OUR, Missing in PROV (This Month)
                if loc_our and not loc_prov:
                    if global_merge == 'left_only':
                        return ['❌ TRULY MISSING in PROV (Globally)']
                    else:
                        return ['📅 Date Cut-off (Found in PROV other month)']

                # Case 2: Active in PROV, Missing in OUR (This Month)
                if not loc_our and loc_prov:
                    if global_merge == 'right_only':
                        return ['❌ TRULY MISSING in OUR (Globally)']
                    else:
                        return ['📅 Date Cut-off (Found in OUR other month)']
                
                # Case 3: Matched in Month, Check Values
                if loc_our and loc_prov:
                    if use_price:
                        p1 = float(row['Price_1']) if pd.notnull(row['Price_1']) else 0.0
                        p2 = float(row['Price_2']) if pd.notnull(row['Price_2']) else 0.0
                        if abs(p1 - p2) > 0.01: errs.append('Price Mismatch')
                    if use_var_a and str(row['User_1']) != str(row['User_2']): errs.append('User Mismatch')
                    if use_var_b and str(row['Add_1']) != str(row['Add_2']): errs.append('Add\'l Mismatch')
                
                return errs if errs else ['OK']

            df_main['Error_List'] = df_main.apply(analyze_main, axis=1)
            df_main['Status'] = df_main['Error_List'].apply(lambda x: ", ".join(x))

            # 6. INVESTIGATION (Updated for new status names)
            df_investigation = df_main[df_main['Status'] != 'OK'].copy()
            
            def investigate_row(row):
                status = row['Status']
                s_prov = row['Date_PROV'].strftime('%Y-%m-%d') if pd.notnull(row['Date_PROV']) else "Unknown"
                s_our = row['Date_OUR'].strftime('%Y-%m-%d') if pd.notnull(row['Date_OUR']) else "Unknown"

                if 'TRULY MISSING in PROV' in status: return "❌ Not found anywhere in PROV"
                if 'Date Cut-off' in status and 'PROV' in status: return f"✅ Found in PROV on {s_prov}"
                
                if 'TRULY MISSING in OUR' in status: return "❌ Not found anywhere in OUR"
                if 'Date Cut-off' in status and 'OUR' in status: return f"✅ Found in OUR on {s_our}"

                return "⚠️ Content Mismatch (Dates OK)"

            if not df_investigation.empty:
                df_investigation['Investigation'] = df_investigation.apply(investigate_row, axis=1)
            
            st.session_state['main_df'] = df_main
            st.session_state['investigation_df'] = df_investigation
            st.session_state['analysis_done'] = True

        # --- DISPLAY RESULTS ---
        if st.session_state['analysis_done']:
            df_main = st.session_state['main_df']
            df_inv = st.session_state['investigation_df']
            
            # Styling for new statuses
            def color_status(val): 
                val_str = str(val)
                if 'OK' in val_str: return 'color: #2e7d32; font-weight: bold;' # Green
                if 'TRULY MISSING' in val_str: return 'color: #d32f2f; font-weight: bold;' # Red
                if 'Date Cut-off' in val_str: return 'color: #ef6c00; font-weight: bold;' # Orange
                return 'color: #d32f2f; font-weight: bold;'

            def color_none(val): return 'color: #d32f2f; font-weight: bold;' if str(val) == "None" else ''

            st.header(f"📊 Main Report: {target_month_name} {target_year}")
            
            if not df_main.empty:
                discrepancies = df_main[df_main['Status'] != 'OK']
                
                # --- METRICS (UPDATED) ---
                total_cnt = len(df_main)
                
                # 1. Truly Missing (Red)
                truly_missing = discrepancies['Status'].str.contains('TRULY MISSING').sum()
                
                # 2. Date Cut-off (Orange)
                date_cutoff = discrepancies['Status'].str.contains('Date Cut-off').sum()
                
                # 3. Price
                price_cnt = 0
                net_diff = 0.0
                if use_price:
                    price_errs = discrepancies[discrepancies['Status'].str.contains('Price')]
                    price_cnt = len(price_errs)
                    net_diff = price_errs['Diff'].sum()
                
                # 4. Content
                content_cnt = discrepancies['Status'].str.contains('User|Add\'l').sum()

                # 5 Columns Layout
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Rows (In Period)", total_cnt)
                m2.metric("❌ TRULY MISSING", truly_missing, delta_color="inverse")
                m3.metric("📅 Date Mismatches", date_cutoff, delta_color="off")
                
                if use_price:
                    m4.metric("Price Mismatches", price_cnt, delta=f"{net_diff:,.2f}")
                else:
                    m4.metric("Price Mismatches", "N/A")
                    
                m5.metric("Content Mismatches", content_cnt, delta_color="inverse")

                # --- VIEW ---
                c_view, c_down = st.columns([1, 4])
                with c_view: show_all = st.checkbox("Show all rows", value=False)
                
                view_main = df_main.copy() if show_all else discrepancies.copy()
                
                if not view_main.empty:
                    view_main['Date_OUR_Str'] = view_main['Date_OUR'].dt.strftime('%Y-%m-%d').fillna("None")
                    view_main['Date_PROV_Str'] = view_main['Date_PROV'].dt.strftime('%Y-%m-%d').fillna("None")
                    
                    cols = ['ID_OUR', 'ID_PROV', 'Date_OUR_Str', 'Date_PROV_Str']
                    renames = {'Date_OUR_Str': 'Date (OUR)', 'Date_PROV_Str': 'Date (PROV)'}
                    
                    if use_price: cols.extend(['Price_1', 'Price_2', 'Diff'])
                    if use_var_a: 
                        cols.extend(['User_1', 'User_2'])
                        renames.update({'User_1': f"{va_col_1} (OUR)", 'User_2': f"{va_col_2} (PROV)"})
                    if use_var_b:
                        cols.extend(['Add_1', 'Add_2'])
                        renames.update({'Add_1': f"{vb_col_1} (OUR)", 'Add_2': f"{vb_col_2} (PROV)"})
                    
                    cols.append('Status')
                    
                    csv_main = view_main[cols].rename(columns=renames).to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Report (CSV)", csv_main, "main_report.csv", "text/csv")

                    st.dataframe(view_main[cols].rename(columns=renames).fillna("None").style.map(color_none).map(color_status, subset=['Status']), use_container_width=True, hide_index=True)
                else:
                    if show_all: st.warning("No rows found.")
                    else: st.success("✅ Clean! No discrepancies.")
            else:
                st.warning(f"No transactions found for {target_month_name} {target_year}.")

            st.write("---")

            st.header("🕵️ Investigation (Lost & Found)")
            if not df_inv.empty:
                cols_inv = ['ID_OUR', 'ID_PROV', 'Investigation', 'Status']
                
                df_inv['Date_OUR_Str'] = df_inv['Date_OUR'].dt.strftime('%Y-%m-%d').fillna("Unknown")
                df_inv['Date_PROV_Str'] = df_inv['Date_PROV'].dt.strftime('%Y-%m-%d').fillna("Unknown")
                
                cols_inv.insert(1, 'Date_OUR_Str')
                cols_inv.insert(3, 'Date_PROV_Str')
                
                renames_inv = {'Date_OUR_Str': 'Date (OUR)', 'Date_PROV_Str': 'Date (PROV)', 'Investigation': 'Global Search Result'}

                def color_res(val):
                    if '✅' in str(val): return 'color: #2e7d32; font-weight: bold;'
                    if '❌' in str(val): return 'color: #d32f2f; font-weight: bold;'
                    return ''

                csv_inv = df_inv[cols_inv].rename(columns=renames_inv).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Investigation (CSV)", csv_inv, "investigation_report.csv", "text/csv")

                st.dataframe(df_inv[cols_inv].rename(columns=renames_inv).fillna("None").style.map(color_res, subset=['Global Search Result']), use_container_width=True, hide_index=True)
            else:
                st.success("Nothing to investigate.")
