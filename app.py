import streamlit as st
import pandas as pd
import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Universal Reconcile v17", layout="wide", page_icon="🧩")

# --- SESSION STATE ---
if 'analysis_done' not in st.session_state: st.session_state['analysis_done'] = False
if 'main_df' not in st.session_state: st.session_state['main_df'] = None
if 'timing_df' not in st.session_state: st.session_state['timing_df'] = None

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
        
        # === A. TARGET PERIOD & ANCHOR ===
        st.subheader("🗓️ 1. Period & Anchor")
        
        # Date Selection Row
        col_per1, col_per2, col_per3, col_per4 = st.columns(4)
        with col_per1:
            target_year = st.selectbox("Target Year", range(2023, 2030), index=3) # Default 2026
        with col_per2:
            months = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 
                      7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
            target_month_name = st.selectbox("Target Month", list(months.values()))
            target_month = list(months.keys())[list(months.values()).index(target_month_name)]
        
        # Date Column Selection
        with col_per3:
            date_col_1 = st.selectbox("Date Column (OUR)", df1.columns)
        with col_per4:
            date_col_2 = st.selectbox("Date Column (PROVIDER)", df2.columns)

        st.write("")
        # Anchor Selection
        k1, k2 = st.columns(2)
        key_col_1 = k1.selectbox(f"Anchor ID (OUR)", df1.columns)
        key_col_2 = k2.selectbox(f"Anchor ID (PROVIDER)", df2.columns)

        # Validation
        if df1[key_col_1].duplicated().any() or df2[key_col_2].duplicated().any():
             st.warning(f"⚠️ Warning: Anchors contain duplicates. Results might be huge.")

        # === B. COMPARISON FIELDS ===
        st.subheader("⚙️ 2. Comparison Fields")
        
        # Price
        use_price = st.checkbox("💰 Compare Price", value=True)
        p_col_1, p_col_2 = None, None
        if use_price:
            pc1, pc2 = st.columns(2)
            p_col_1 = pc1.selectbox("Price (OUR)", df1.columns, key="p1")
            p_col_2 = pc2.selectbox("Price (PROVIDER)", df2.columns, key="p2")
        
        # User
        use_var_a = st.checkbox("👤 Compare User", value=False)
        va_col_1, va_col_2 = None, None
        if use_var_a:
            vc1, vc2 = st.columns(2)
            va_col_1 = vc1.selectbox("User (OUR)", df1.columns, key="va1")
            va_col_2 = vc2.selectbox("User (PROVIDER)", df2.columns, key="va2")

        # Additional
        use_var_b = st.checkbox("🧩 Compare Additional", value=False)
        vb_col_1, vb_col_2 = None, None
        if use_var_b:
            vb1, vb2 = st.columns(2)
            vb_col_1 = vb1.selectbox("Add'l (OUR)", df1.columns, key="vb1")
            vb_col_2 = vb2.selectbox("Add'l (PROVIDER)", df2.columns, key="vb2")

        st.markdown("---")

        # --- RUN ANALYSIS ---
        if st.button("🚀 Run Analysis", type="primary"):
            
            # --- 1. DATE PREPROCESSING ---
            # Convert dates to datetime objects using errors='coerce' to handle bad formats safely
            data1 = pd.DataFrame()
            data2 = pd.DataFrame()
            
            try:
                data1['_date_obj'] = pd.to_datetime(df1[date_col_1], dayfirst=True, errors='coerce')
                data2['_date_obj'] = pd.to_datetime(df2[date_col_2], dayfirst=True, errors='coerce')
            except Exception as e:
                st.error(f"Date Parsing Error: {e}")
                st.stop()

            # --- 2. DATA PREP ---
            # Anchors
            data1['_anchor'] = clean_string_key(df1[key_col_1])
            data2['_anchor'] = clean_string_key(df2[key_col_2])
            
            # Visible Fields
            data1['Anchor_Disp_1'] = df1[key_col_1].astype(str)
            data2['Anchor_Disp_2'] = df2[key_col_2].astype(str)
            data1['Date_Disp_1'] = data1['_date_obj'].dt.strftime('%Y-%m-%d %H:%M')
            data2['Date_Disp_2'] = data2['_date_obj'].dt.strftime('%Y-%m-%d %H:%M')

            # Comparison Data
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
            merged = pd.merge(data1, data2, on='_anchor', how='outer', indicator=True)

            # --- 4. DATE LOGIC & FILTERING ---
            
            # Helper to check if a row belongs to Target Month/Year
            def is_in_target(dt_series):
                return (dt_series.dt.month == target_month) & (dt_series.dt.year == target_year)

            merged['In_Target_1'] = is_in_target(merged['_date_obj_x'])
            merged['In_Target_2'] = is_in_target(merged['_date_obj_y'])

            # --- 5. SPLITTING THE DATASETS ---
            
            # MAIN REPORT CRITERIA:
            # Row involves the target month if:
            # (Exists in 1 AND Is Target in 1) OR (Exists in 2 AND Is Target in 2)
            # BUT we exclude cases where it exists in BOTH, one is Target, one is NOT (that goes to Timing)
            
            # Let's simplify:
            # 1. Timing Difference: Exists in BOTH, but only ONE date matches target month.
            timing_mask = (merged['_merge'] == 'both') & (merged['In_Target_1'] != merged['In_Target_2'])
            
            # 2. Main Report: Everything else that touches the target month.
            # (In Target 1 OR In Target 2) AND NOT Timing Mask
            relevant_mask = (merged['In_Target_1'] | merged['In_Target_2']) & (~timing_mask)
            
            df_main = merged[relevant_mask].copy()
            df_timing = merged[timing_mask].copy()

            # --- 6. CALCULATE STATUS (Shared Logic) ---
            def calc_status(df):
                if use_price:
                    df['Diff'] = (df['Price_1'].fillna(0) - df['Price_2'].fillna(0)).round(2)
                
                def analyze(row):
                    errs = []
                    # Missing Logic
                    if row['_merge'] == 'left_only': return ['Missing in PROVIDER']
                    if row['_merge'] == 'right_only': return ['Missing in OUR']
                    
                    # Comparison Logic (Only for matches)
                    if row['_merge'] == 'both':
                        if use_price:
                            p1 = float(row['Price_1']) if pd.notnull(row['Price_1']) else 0.0
                            p2 = float(row['Price_2']) if pd.notnull(row['Price_2']) else 0.0
                            if abs(p1 - p2) > 0.01: errs.append('Price Mismatch')
                        if use_var_a and str(row['User_1']) != str(row['User_2']): errs.append('User Mismatch')
                        if use_var_b and str(row['Add_1']) != str(row['Add_2']): errs.append('Add\'l Mismatch')
                    
                    return errs if errs else ['OK']

                df['Error_List'] = df.apply(analyze, axis=1)
                df['Status'] = df['Error_List'].apply(lambda x: ", ".join(x))
                return df

            if not df_main.empty: df_main = calc_status(df_main)
            if not df_timing.empty: df_timing = calc_status(df_timing)

            # Store in Session
            st.session_state['main_df'] = df_main
            st.session_state['timing_df'] = df_timing
            st.session_state['analysis_done'] = True

        # --- DISPLAY RESULTS ---
        if st.session_state['analysis_done']:
            df_main = st.session_state['main_df']
            df_timing = st.session_state['timing_df']

            # Styling Functions
            def color_none(val): return 'color: #d32f2f; font-weight: bold;' if str(val) == "None" else ''
            def color_status(val): return 'color: #2e7d32; font-weight: bold;' if val == 'OK' else 'color: #d32f2f; font-weight: bold;'

            # ================= MAIN REPORT =================
            st.header(f"📊 Main Report: {target_month_name} {target_year}")
            
            if not df_main.empty:
                # Metrics
                discrepancies = df_main[df_main['Status'] != 'OK']
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Rows", len(df_main))
                m1.caption(f"Transactions belonging to {target_month_name}")
                m2.metric("Missing Rows", len(discrepancies[discrepancies['Status'].str.contains('Missing')]), delta_color="inverse")
                
                if use_price:
                    p_errs = discrepancies[discrepancies['Status'].str.contains('Price')]
                    m3.metric("Price Mismatches", len(p_errs), delta=f"{p_errs['Diff'].sum():,.2f}")
                
                other_err = 0
                if use_var_a or use_var_b:
                    other_err = discrepancies['Status'].str.contains('Mismatch').sum() - (len(p_errs) if use_price else 0)
                    if other_err < 0: other_err = 0 # Safety fix
                    m4.metric("Content Mismatches", other_err, delta_color="inverse")

                # Table
                show_all = st.checkbox("Show all rows (Main Report)", value=False, key="chk_main")
                view_df = df_main.copy() if show_all else discrepancies.copy()
                
                if not view_df.empty:
                    view_df = view_df.sort_values(by=['Status'], ascending=False)
                    
                    # Columns
                    cols = ['Anchor_Disp_1', 'Anchor_Disp_2']
                    renames = {'Anchor_Disp_1': f"{key_col_1} (OUR)", 'Anchor_Disp_2': f"{key_col_2} (PROV)"}
                    
                    if use_price: cols.extend(['Price_1', 'Price_2', 'Diff'])
                    if use_var_a: 
                        renames.update({'User_1': f"{va_col_1} (OUR)", 'User_2': f"{va_col_2} (PROV)"})
                        cols.extend(['User_1', 'User_2'])
                    if use_var_b: 
                        renames.update({'Add_1': f"{vb_col_1} (OUR)", 'Add_2': f"{vb_col_2} (PROV)"})
                        cols.extend(['Add_1', 'Add_2'])
                    
                    cols.append('Status')
                    
                    # Display
                    dl_df = view_df[cols].rename(columns=renames)
                    csv = dl_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Main Report", csv, "main_report.csv", "text/csv", key='dl_main')
                    
                    st.dataframe(dl_df.fillna("None").style.map(color_none).map(color_status, subset=['Status']), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ Main Report Clean!")
            else:
                st.info("No transactions found for this month.")

            st.write("---")

            # ================= TIMING DIFFERENCES REPORT =================
            st.header("📅 Timing Differences (Cross-Month Matches)")
            st.markdown(f"Transactions found in both files, but one falls **outside** {target_month_name} {target_year}.")

            if not df_timing.empty:
                t1, t2 = st.columns(2)
                t1.metric("Timing Discrepancies", len(df_timing))
                if use_price:
                    t2.metric("Net Diff (Timing)", f"{df_timing['Diff'].sum():,.2f}")

                # Table Prep
                cols_t = ['Anchor_Disp_1', 'Date_Disp_1', 'Anchor_Disp_2', 'Date_Disp_2']
                renames_t = {
                    'Anchor_Disp_1': f"ID (OUR)", 'Date_Disp_1': f"Date (OUR)",
                    'Anchor_Disp_2': f"ID (PROV)", 'Date_Disp_2': f"Date (PROV)"
                }
                
                if use_price: cols_t.extend(['Price_1', 'Price_2', 'Diff'])
                if use_var_a: 
                    cols_t.extend(['User_1', 'User_2'])
                    renames_t.update({'User_1': f"User (OUR)", 'User_2': f"User (PROV)"})
                
                cols_t.append('Status')

                # Highlight Logic for Dates
                # We want to highlight the date that is DIFFERENT from the target month
                def highlight_timing(row):
                    styles = [''] * len(row)
                    # Logic is complex for visual styling row-by-row in pandas style without index access
                    # So we keep it simple: Color the Date columns if they exist
                    return styles

                view_timing = df_timing[cols_t].rename(columns=renames_t)
                
                csv_t = view_timing.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Timing Report", csv_t, "timing_report.csv", "text/csv", key='dl_timing')

                st.dataframe(
                    view_timing.fillna("None").style.map(color_none).map(color_status, subset=['Status']),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No timing discrepancies found (all matches are within the same month).")
