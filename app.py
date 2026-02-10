import streamlit as st
import pandas as pd
import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v20", layout="wide", page_icon="🧩")

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
    return series.astype(str).fillna("").str.strip()

def clean_compare_string(series):
    return series.astype(str).fillna("").str.strip()

def super_robust_date_parse(series):
    """
    Brute-force date parsing.
    1. Clean strings (remove T, Z).
    2. Try multiple strategies.
    3. Strip timezones.
    """
    # 1. Force string and clean artifacts
    s = series.astype(str).str.strip()
    
    # Remove 'Z' (UTC marker) and 'T' (ISO separator) to simplify parsing
    # '2026-01-31T20:57:37.904623Z' -> '2026-01-31 20:57:37.904623'
    s = s.str.replace('Z', '', regex=False).str.replace('T', ' ', regex=False)
    
    # 2. Strategy A: Pandas auto-magic with UTC=True (handles most ISO)
    try:
        dt = pd.to_datetime(s, dayfirst=True, utc=True, errors='coerce')
    except:
        # 3. Strategy B: Fallback if mixed garbage
        dt = pd.to_datetime(s, errors='coerce')

    # 4. CRITICAL: Kill Timezones (Make everything naive)
    if dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
        
    return dt

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
            target_year = st.selectbox("Target Year", range(2023, 2030), index=3) # 2026
        with col_per2:
            months = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 
                      7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
            target_month_name = st.selectbox("Target Month", list(months.values()))
            target_month = list(months.keys())[list(months.values()).index(target_month_name)]
        
        with col_per3:
            date_col_1 = st.selectbox("Date Column (OUR)", df1.columns)
        with col_per4:
            date_col_2 = st.selectbox("Date Column (PROVIDER)", df2.columns)

        st.write("")
        anchor_help = "Must be UNIQUE ID."
        k1, k2, k_buff = st.columns([2, 2, 3])
        with k1: key_col_1 = st.selectbox(f"Anchor ID (OUR)", df1.columns, help=anchor_help)
        with k2: key_col_2 = st.selectbox(f"Anchor ID (PROVIDER)", df2.columns, help=anchor_help)
        
        if df1[key_col_1].duplicated().any() or df2[key_col_2].duplicated().any():
             st.warning(f"⚠️ Warning: Anchors contain duplicates. Results might be inaccurate.")

        # === B. COMPARISON FIELDS ===
        st.write("")
        st.subheader("⚙️ 2. Comparison Fields")
        
        use_price = st.checkbox("💰 Compare Price", value=True)
        p_col_1, p_col_2 = None, None
        if use_price:
            pc1, pc2, pc3 = st.columns([2, 2, 3])
            with pc1: p_col_1 = st.selectbox("Price (OUR)", df1.columns, key="p1")
            with pc2: p_col_2 = st.selectbox("Price (PROVIDER)", df2.columns, key="p2")
        
        st.write("")
        use_var_a = st.checkbox("👤 Compare User", value=False)
        va_col_1, va_col_2 = None, None
        if use_var_a:
            vc1, vc2, vc3 = st.columns([2, 2, 3])
            with vc1: va_col_1 = st.selectbox("User (OUR)", df1.columns, key="va1")
            with vc2: va_col_2 = st.selectbox("User (PROVIDER)", df2.columns, key="va2")

        st.write("")
        use_var_b = st.checkbox("🧩 Compare Additional", value=False)
        vb_col_1, vb_col_2 = None, None
        if use_var_b:
            vb1, vb2, vb3 = st.columns([2, 2, 3])
            with vb1: vb_col_1 = st.selectbox("Add'l (OUR)", df1.columns, key="vb1")
            with vb2: vb_col_2 = st.selectbox("Add'l (PROVIDER)", df2.columns, key="vb2")

        st.markdown("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # --- VALIDATION ---
            errors_found = []
            if use_var_a and (va_col_1 == key_col_1 or va_col_2 == key_col_2): errors_found.append("❌ User column matches Anchor.")
            if errors_found:
                for e in errors_found: st.error(e)
                st.stop()

            # --- 1. SUPER ROBUST DATE PARSING ---
            with st.spinner("Parsing dates..."):
                df1['_date_obj'] = super_robust_date_parse(df1[date_col_1])
                df2['_date_obj'] = super_robust_date_parse(df2[date_col_2])

            # Debug check
            failed_1 = df1['_date_obj'].isna().sum()
            failed_2 = df2['_date_obj'].isna().sum()
            if failed_1 > 0: st.toast(f"⚠️ Could not read {failed_1} dates in OUR file.", icon="⚠️")
            if failed_2 > 0: st.toast(f"⚠️ Could not read {failed_2} dates in PROVIDER file.", icon="⚠️")

            # --- 2. PREPARE DATA ---
            data1 = pd.DataFrame()
            data2 = pd.DataFrame()
            
            data1['_anchor'] = clean_string_key(df1[key_col_1])
            data2['_anchor'] = clean_string_key(df2[key_col_2])
            
            # Keep display data
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

            # --- 3. GLOBAL MERGE ---
            full_merge = pd.merge(data1, data2, on='_anchor', how='outer', indicator=True)

            # --- 4. DATE FILTERING (CUT-OFF) ---
            def check_month(dt):
                if pd.isna(dt): return False
                return (dt.month == target_month) and (dt.year == target_year)

            full_merge['In_Month_OUR'] = full_merge['Date_OUR'].apply(check_month)
            full_merge['In_Month_PROV'] = full_merge['Date_PROV'].apply(check_month)

            # Active in Main Report if present in Target Month on EITHER side
            main_mask = full_merge['In_Month_OUR'] | full_merge['In_Month_PROV']
            df_main = full_merge[main_mask].copy()

            # --- 5. ANALYZE MAIN REPORT ---
            if use_price:
                df_main['Diff'] = (df_main['Price_1'].fillna(0) - df_main['Price_2'].fillna(0)).round(2)

            def analyze_main(row):
                errs = []
                # Local Existence Check
                loc_our = row['In_Month_OUR']
                loc_prov = row['In_Month_PROV']

                if loc_our and not loc_prov:
                    return ['Missing in PROVIDER (This Month)']
                if not loc_our and loc_prov:
                    return ['Missing in OUR (This Month)']
                
                # Compare Values
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

            # --- 6. INVESTIGATION REPORT ---
            df_investigation = df_main[df_main['Status'] != 'OK'].copy()
            
            def investigate_row(row):
                status = row['Status']
                
                # Helpers to safely get date string or "Unknown"
                d_prov = row['Date_PROV']
                d_our = row['Date_OUR']
                
                # Logic: If NaT (Not a Time), we found the ID but don't know the date
                if pd.notnull(d_prov): s_prov = d_prov.strftime('%Y-%m-%d')
                else: s_prov = "Unknown Date"
                
                if pd.notnull(d_our): s_our = d_our.strftime('%Y-%m-%d')
                else: s_our = "Unknown Date"

                # Case 1: Missing in PROV (This Month)
                if 'Missing in PROVIDER' in status:
                    if row['_merge'] == 'both':
                        return f"✅ Found in PROV: {s_prov}"
                    else:
                        return "❌ Not found anywhere in PROV"

                # Case 2: Missing in OUR (This Month)
                if 'Missing in OUR' in status:
                    if row['_merge'] == 'both':
                         return f"✅ Found in OUR: {s_our}"
                    else:
                         return "❌ Not found anywhere in OUR"

                return "⚠️ Value Mismatch (Dates OK)"

            if not df_investigation.empty:
                df_investigation['Investigation'] = df_investigation.apply(investigate_row, axis=1)
            
            # Save State
            st.session_state['main_df'] = df_main
            st.session_state['investigation_df'] = df_investigation
            st.session_state['analysis_done'] = True

        # --- DISPLAY RESULTS ---
        if st.session_state['analysis_done']:
            df_main = st.session_state['main_df']
            df_inv = st.session_state['investigation_df']
            
            def color_none(val): return 'color: #d32f2f; font-weight: bold;' if str(val) == "None" else ''
            def color_status(val): return 'color: #2e7d32; font-weight: bold;' if 'OK' in str(val) else 'color: #d32f2f; font-weight: bold;'

            # 1. MAIN REPORT
            st.header(f"📊 Main Report: {target_month_name} {target_year}")
            
            if not df_main.empty:
                discrepancies = df_main[df_main['Status'] != 'OK']
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Rows (This Month)", len(df_main))
                m2.metric("Discrepancies", len(discrepancies), delta_color="inverse")
                if use_price:
                    diff_val = discrepancies[discrepancies['Status'].str.contains('Price')]['Diff'].sum()
                    m3.metric("Net Price Difference", f"{diff_val:,.2f}")

                show_all = st.checkbox("Show all rows", value=False)
                view_main = df_main.copy() if show_all else discrepancies.copy()
                
                cols = ['ID_OUR', 'ID_PROV']
                renames = {}
                if use_price: cols.extend(['Price_1', 'Price_2', 'Diff'])
                if use_var_a: 
                    cols.extend(['User_1', 'User_2'])
                    renames.update({'User_1': f"{va_col_1} (OUR)", 'User_2': f"{va_col_2} (PROV)"})
                if use_var_b:
                    cols.extend(['Add_1', 'Add_2'])
                    renames.update({'Add_1': f"{vb_col_1} (OUR)", 'Add_2': f"{vb_col_2} (PROV)"})
                
                cols.append('Status')
                
                st.dataframe(
                    view_main[cols].rename(columns=renames).fillna("None").style.map(color_none).map(color_status, subset=['Status']),
                    use_container_width=True, hide_index=True
                )
                
                csv_main = view_main[cols].rename(columns=renames).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Main Report", csv_main, "main_report.csv", "text/csv")
            else:
                st.warning("No transactions found for this month.")

            st.write("---")

            # 2. INVESTIGATION REPORT
            st.header("🕵️ Investigation (Lost & Found)")
            if not df_inv.empty:
                st.info(f"Checking {len(df_inv)} discrepancies against other months...")
                
                cols_inv = ['ID_OUR', 'ID_PROV', 'Investigation', 'Status']
                
                # Context Dates
                df_inv['Date_OUR_Str'] = df_inv['Date_OUR'].dt.strftime('%Y-%m-%d').fillna("Unknown")
                df_inv['Date_PROV_Str'] = df_inv['Date_PROV'].dt.strftime('%Y-%m-%d').fillna("Unknown")
                
                cols_inv.insert(1, 'Date_OUR_Str')
                cols_inv.insert(3, 'Date_PROV_Str')
                
                renames_inv = {
                    'Date_OUR_Str': 'Date (OUR)',
                    'Date_PROV_Str': 'Date (PROV)',
                    'Investigation': 'Result'
                }

                def color_res(val):
                    if '✅' in str(val): return 'color: #2e7d32; font-weight: bold;'
                    if '❌' in str(val): return 'color: #d32f2f; font-weight: bold;'
                    return ''

                st.dataframe(
                    df_inv[cols_inv].rename(columns=renames_inv).fillna("None").style.map(color_res, subset=['Result']),
                    use_container_width=True, hide_index=True
                )
                
                csv_inv = df_inv[cols_inv].rename(columns=renames_inv).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Investigation Report", csv_inv, "investigation_report.csv", "text/csv")
            else:
                st.success("Nothing to investigate.")
