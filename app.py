import streamlit as st
import pandas as pd
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v22", layout="wide", page_icon="🧩")

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

def nuclear_date_parser(val):
    """
    Regex-based parser. Ignores timezones and garbage.
    Focuses purely on extracting YYYY-MM-DD.
    """
    s = str(val).strip()
    
    # 1. Try finding YYYY-MM-DD
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if iso_match:
        try:
            return pd.to_datetime(iso_match.group(1))
        except:
            pass
            
    # 2. Try finding DD.MM.YYYY
    euro_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', s)
    if euro_match:
        try:
            return pd.to_datetime(euro_match.group(1), dayfirst=True)
        except:
            pass

    # 3. Fallback
    try:
        return pd.to_datetime(s, errors='coerce')
    except:
        return pd.NaT

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
            
            # 1. PARSE DATES (Nuclear)
            df1['_date_obj'] = df1[date_col_1].apply(nuclear_date_parser)
            df2['_date_obj'] = df2[date_col_2].apply(nuclear_date_parser)

            # 2. PREPARE DATA
            data1 = pd.DataFrame()
            data2 = pd.DataFrame()
            
            data1['_anchor'] = clean_string_key(df1[key_col_1])
            data2['_anchor'] = clean_string_key(df2[key_col_2])
            
            # Display Columns
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

            # 4. FILTERING (Target Month)
            def check_month(dt):
                if pd.isna(dt): return False
                return (dt.month == target_month) and (dt.year == target_year)

            full_merge['In_Month_OUR'] = full_merge['Date_OUR'].apply(check_month)
            full_merge['In_Month_PROV'] = full_merge['Date_PROV'].apply(check_month)

            main_mask = full_merge['In_Month_OUR'] | full_merge['In_Month_PROV']
            df_main = full_merge[main_mask].copy()

            # 5. ANALYZE MAIN
            if use_price:
                df_main['Diff'] = (df_main['Price_1'].fillna(0) - df_main['Price_2'].fillna(0)).round(2)

            def analyze_main(row):
                errs = []
                loc_our = row['In_Month_OUR']
                loc_prov = row['In_Month_PROV']

                # Missing checks based on Target Month
                if loc_our and not loc_prov: return ['Missing in PROVIDER (This Month)']
                if not loc_our and loc_prov: return ['Missing in OUR (This Month)']
                
                # Mismatch checks
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

            # 6. INVESTIGATION (Everything NOT OK in Main goes here)
            df_investigation = df_main[df_main['Status'] != 'OK'].copy()
            
            def investigate_row(row):
                status = row['Status']
                d_prov = row['Date_PROV']
                d_our = row['Date_OUR']
                
                s_prov = d_prov.strftime('%Y-%m-%d') if pd.notnull(d_prov) else "Unknown"
                s_our = d_our.strftime('%Y-%m-%d') if pd.notnull(d_our) else "Unknown"

                # If it's missing in PROV locally, check global
                if 'Missing in PROVIDER' in status:
                    if row['_merge'] == 'both': return f"✅ Found in PROV: {s_prov}"
                    else: return "❌ Not found anywhere in PROV"

                # If it's missing in OUR locally, check global
                if 'Missing in OUR' in status:
                    if row['_merge'] == 'both': return f"✅ Found in OUR: {s_our}"
                    else: return "❌ Not found anywhere in OUR"

                return "⚠️ Mismatch (Data issue)"

            if not df_investigation.empty:
                df_investigation['Investigation'] = df_investigation.apply(investigate_row, axis=1)
            
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

                # --- VIEW CONTROLS ---
                c_view, c_down = st.columns([1, 4])
                with c_view:
                    show_all = st.checkbox("Show all rows", value=False)
                
                # Filter Data
                view_main = df_main.copy() if show_all else discrepancies.copy()
                
                # Columns
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
                
                # Download Button
                csv_main = view_main[cols].rename(columns=renames).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report (CSV)", csv_main, "main_report.csv", "text/csv")

                # Table
                st.dataframe(
                    view_main[cols].rename(columns=renames).fillna("None").style.map(color_none).map(color_status, subset=['Status']),
                    use_container_width=True, hide_index=True
                )
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
                
                renames_inv = {'Date_OUR_Str': 'Date (OUR)', 'Date_PROV_Str': 'Date (PROV)', 'Investigation': 'Global Search Result'}

                def color_res(val):
                    if '✅' in str(val): return 'color: #2e7d32; font-weight: bold;'
                    if '❌' in str(val): return 'color: #d32f2f; font-weight: bold;'
                    return ''

                # Download Investigation
                csv_inv = df_inv[cols_inv].rename(columns=renames_inv).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Investigation (CSV)", csv_inv, "investigation_report.csv", "text/csv")

                st.dataframe(
                    df_inv[cols_inv].rename(columns=renames_inv).fillna("None").style.map(color_res, subset=['Global Search Result']),
                    use_container_width=True, hide_index=True
                )
            else:
                st.success("Nothing to investigate (Everything matched in the main report).")
