import streamlit as st
import pandas as pd
import re

# --- PAGE CONFIG (CSS INJECTION FOR UI POLISH) ---
st.set_page_config(page_title="Сверка Данных v29", layout="wide", page_icon="✨")

# Custom CSS to make the main button prominent and center it
st.markdown("""
<style>
div.stButton > button:first-child {
    width: 100%;
    height: 3em;
    font-size: 18px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


# --- SESSION STATE ---
if 'analysis_done' not in st.session_state: st.session_state['analysis_done'] = False
if 'main_df' not in st.session_state: st.session_state['main_df'] = None
if 'investigation_df' not in st.session_state: st.session_state['investigation_df'] = None

st.title("✨ Инструмент Сверки Данных (Reconciliation Tool)")
st.markdown("Простой и точный способ сравнить два отчета и найти расхождения.")

# --- HELPER FUNCTIONS (LOGIC UNCHANGED) ---
@st.cache_data
def load_data(file):
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file, low_memory=False)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Ошибка чтения файла {file.name}: {e}")
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
    # Fallback
    try: return pd.to_datetime(s, errors='coerce')
    except: return pd.NaT

def find_date_col(cols):
    for c in cols:
        if 'date' in c.lower() or 'time' in c.lower() or 'created' in c.lower() or 'at' in c.lower() or 'дата' in c.lower():
            return c
    return cols[0]

# ================= UI STEP 1: UPLOAD FILES =================
st.header("📂 Шаг 1. Загрузите файлы для сравнения")
st.markdown("Выберите два файла (CSV или Excel), которые нужно сверить.")

c1, c2 = st.columns(2)
# Humanized labels and helpful captions
with c1: 
    f1 = st.file_uploader("Наши данные (из внутренней системы)", key="f1", help="Загрузите файл, который вы считаете эталонным (например, выгрузка из вашей CRM/ERP).")
with c2: 
    f2 = st.file_uploader("Данные партнёра (внешний отчёт)", key="f2", help="Загрузите файл, полученный от партнера, провайдера или платежной системы.")

# --- DATA LOADING & PREP ---
df1, df2 = None, None
files_ready = False

if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)
    if df1 is not None and df2 is not None:
        files_ready = True
    else:
        st.warning("Не удалось прочитать один из файлов. Проверьте формат.")

if files_ready:
    st.divider()

    # ================= UI STEP 2: PERIOD & LINKING =================
    st.header("🔗 Шаг 2. Настройка периода и связей")
    st.markdown("Укажите, за какой период мы сверяем данные и как связать строки между двумя файлами.")
    
    # --- A. Period Selection ---
    st.subheader("📅 Период сверки")
    col_per1, col_per2 = st.columns(2)
    with col_per1:
        target_year = st.selectbox("Год", range(2023, 2030), index=3)
    with col_per2:
        months = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь", 
                  7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}
        target_month_name = st.selectbox("Месяц", list(months.values()))
        target_month = list(months.keys())[list(months.values()).index(target_month_name)]

    st.write("") # Spacer

    # --- B. Columns Mapping ---
    st.subheader("🔑 Ключевые поля для сопоставления")
    
    # Auto-detect dates
    idx_d1 = list(df1.columns).index(find_date_col(df1.columns))
    idx_d2 = list(df2.columns).index(find_date_col(df2.columns))

    col_map1, col_map2 = st.columns(2)
    
    # Column Mapping Block 1 (Our Data)
    with col_map1:
        st.markdown("##### 🏛️ В Наших данных")
        date_col_1 = st.selectbox("Где указана дата операции?", df1.columns, index=idx_d1, help="Выберите столбец, содержащий дату и время транзакции.")
        # Humanized "Anchor" label + Tooltip
        key_col_1 = st.selectbox("Поле для сопоставления (Уникальный ID)", df1.columns, help="⚠️ Критически важно! Выберите столбец с уникальным номером (ID заказа, транзакции), который должен совпадать в обоих файлах.")
        if df1[key_col_1].duplicated().any():
             st.warning(f"⚠️ Внимание: В столбце '{key_col_1}' найдены дубликаты. Это может повлиять на точность.")

    # Column Mapping Block 2 (Provider Data)
    with col_map2:
        st.markdown("##### 🤝 В Данных партнёра")
        date_col_2 = st.selectbox("Где указана дата операции? ", df2.columns, index=idx_d2, help="Выберите столбец с датой в файле партнера.")
        key_col_2 = st.selectbox("Поле для сопоставления (Уникальный ID) ", df2.columns, help="Выберите столбец в файле партнера, который соответствует вашему уникальному ID.")
        if df2[key_col_2].duplicated().any():
             st.warning(f"⚠️ Внимание: В столбце '{key_col_2}' найдены дубликаты.")

    st.divider()

    # ================= UI STEP 3: COMPARISON FIELDS =================
    st.header("⚙️ Шаг 3. Что проверять?")
    st.markdown("Выберите, какие именно данные нужно сравнивать, если ID совпали.")

    # Using extenders/columns to organize checks clearly
    
    # 1. Price Check
    use_price = st.checkbox("💰 Сверять Сумму/Цену", value=True, help="Сравнить финансовые значения.")
    p_col_1, p_col_2 = None, None
    if use_price:
        pc1, pc2 = st.columns(2)
        with pc1: p_col_1 = st.selectbox("Столбец с суммой (У нас)", df1.columns, key="p1")
        with pc2: p_col_2 = st.selectbox("Столбец с суммой (У партнёра)", df2.columns, key="p2")
    
    st.write("") # Spacer

    # 2. User/Text Check
    use_var_a = st.checkbox("👤 Сверять Пользователя / Текстовое поле А", value=False, help="Сравнить текстовые данные (например, Email клиента или ID менеджера).")
    va_col_1, va_col_2 = None, None
    if use_var_a:
        vc1, vc2 = st.columns(2)
        with vc1: va_col_1 = st.selectbox("Текстовое поле (У нас)", df1.columns, key="va1")
        with vc2: va_col_2 = st.selectbox("Текстовое поле (У партнёра)", df2.columns, key="va2")

    st.write("") # Spacer

    # 3. Additional Check
    use_var_b = st.checkbox("🧩 Сверять Дополнительное поле Б (например, Статус)", value=False, help="Сравнить еще одно поле (например, статус заказа).")
    vb_col_1, vb_col_2 = None, None
    add_field_name = "Доп. поле" 
    if use_var_b:
        vb1, vb2 = st.columns(2)
        with vb1: vb_col_1 = st.selectbox("Доп. поле (У нас)", df1.columns, key="vb1")
        with vb2: vb_col_2 = st.selectbox("Доп. поле (У партнёра)", df2.columns, key="vb2")
        add_field_name = vb_col_1 # Dynamic name capture

    st.divider()

    # ================= UI STEP 4: RUN ACTION =================
    
    # Readiness Checklist (Micro-feedback)
    st.markdown("#### Готовность к сверке:")
    ready_col1, ready_col2, ready_col3 = st.columns(3)
    with ready_col1: st.write("✅ Файлы загружены")
    with ready_col2: st.write(f"✅ Период: {target_month_name} {target_year}")
    with ready_col3: st.write(f"✅ Связь по ID настроена")

    st.write("") # Extra space before big button
    
    # Centered, Prominent Button (Styled via CSS at the top)
    b_c1, b_c2, b_c3 = st.columns([1, 2, 1])
    with b_c2:
        run_pressed = st.button("🚀 Запустить сверку данных", type="primary")

    if run_pressed:
        with st.spinner("⏳ Идёт анализ данных... Пожалуйста, подождите."):
            # --- LOGIC START (SAME AS v28) ---
            
            # 1. PARSE DATES
            df1['_date_obj'] = df1[date_col_1].apply(nuclear_date_parser)
            df2['_date_obj'] = df2[date_col_2].apply(nuclear_date_parser)
            
            if df1['_date_obj'].notna().sum() == 0:
                st.error(f"❌ Ошибка: Не удалось распознать даты в вашем файле (столбец '{date_col_1}').")
                st.stop()
            if df2['_date_obj'].notna().sum() == 0:
                st.error(f"❌ Ошибка: Не удалось распознать даты в файле партнёра (столбец '{date_col_2}').")
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

            # 5. ANALYZE MAIN (MATRIX LOGIC)
            if use_price:
                df_main['Diff'] = (df_main['Price_1'].fillna(0) - df_main['Price_2'].fillna(0)).round(2)

            def analyze_row_matrix(row):
                res = {
                    'Status_Exist': 'OK',
                    'Status_Price': '',
                    'Status_User': '',
                    f'Status_{add_field_name}': ''
                }
                
                loc_our = row['In_Month_OUR']
                loc_prov = row['In_Month_PROV']
                global_merge = row['_merge']
                
                # --- 1. EXISTENCE CHECK ---
                is_present_globally = False
                
                if loc_our and not loc_prov:
                    if global_merge == 'left_only':
                        res['Status_Exist'] = '❌ Отсутствует у партнёра (Вообще)'
                        return pd.Series(res)
                    else:
                        res['Status_Exist'] = '📅 Не совпадает дата (Найдено у партнёра в другом месяце)'
                        is_present_globally = True

                elif not loc_our and loc_prov:
                    if global_merge == 'right_only':
                        res['Status_Exist'] = '❌ Отсутствует у нас (Вообще)'
                        return pd.Series(res)
                    else:
                        res['Status_Exist'] = '📅 Не совпадает дата (Найдено у нас в другом месяце)'
                        is_present_globally = True
                
                else:
                    is_present_globally = True

                # --- 2. CONTENT CHECK ---
                if is_present_globally:
                    if use_price:
                        p1 = float(row['Price_1']) if pd.notnull(row['Price_1']) else 0.0
                        p2 = float(row['Price_2']) if pd.notnull(row['Price_2']) else 0.0
                        if abs(p1 - p2) > 0.01:
                            res['Status_Price'] = 'Ошибка в сумме'
                        else:
                            res['Status_Price'] = 'OK'
                    
                    if use_var_a:
                        if str(row['User_1']) != str(row['User_2']):
                            res['Status_User'] = 'Ошибка в текстовом поле А'
                        else:
                            res['Status_User'] = 'OK'

                    if use_var_b:
                        if str(row['Add_1']) != str(row['Add_2']):
                            res[f'Status_{add_field_name}'] = f'Ошибка в поле "{add_field_name}"'
                        else:
                            res[f'Status_{add_field_name}'] = 'OK'

                return pd.Series(res)

            status_cols = df_main.apply(analyze_row_matrix, axis=1)
            df_main = pd.concat([df_main, status_cols], axis=1)

            def is_dirty(row):
                if 'Отсутствует' in row['Status_Exist']: return True
                if 'Не совпадает дата' in row['Status_Exist']: return True
                if use_price and 'Ошибка' in str(row.get('Status_Price', '')): return True
                if use_var_a and 'Ошибка' in str(row.get('Status_User', '')): return True
                if use_var_b and 'Ошибка' in str(row.get(f'Status_{add_field_name}', '')): return True
                return False

            df_main['Is_Error'] = df_main.apply(is_dirty, axis=1)
            st.session_state['main_df'] = df_main
            
            # Investigation Logic (Humanized)
            df_investigation = df_main[df_main['Status_Exist'].str.contains('Отсутствует') | df_main['Status_Exist'].str.contains('Не совпадает дата')].copy()
            
            def investigate_row(row):
                status = row['Status_Exist']
                s_prov = row['Date_PROV'].strftime('%d.%m.%Y') if pd.notnull(row['Date_PROV']) else "Неизвестно"
                s_our = row['Date_OUR'].strftime('%d.%m.%Y') if pd.notnull(row['Date_OUR']) else "Неизвестно"

                if 'Отсутствует у партнёра' in status: return "❌ Не найдено в файле партнёра"
                if 'Найдено у партнёра' in status: return f"✅ Найдено у партнёра, дата: {s_prov}"
                
                if 'Отсутствует у нас' in status: return "❌ Не найдено в нашем файле"
                if 'Найдено у нас' in status: return f"✅ Найдено у нас, дата: {s_our}"
                return ""

            if not df_investigation.empty:
                df_investigation['Investigation'] = df_investigation.apply(investigate_row, axis=1)
            
            st.session_state['investigation_df'] = df_investigation
            st.session_state['analysis_done'] = True
            # --- LOGIC END ---

# ================= RESULTS DISPLAY (HUMANIZED) =================
if st.session_state['analysis_done']:
    st.divider()
    df_main = st.session_state['main_df']
    df_inv = st.session_state['investigation_df']
    
    # Styling (Humanized friendly colors)
    def color_cells(val):
        s = str(val)
        if 'Отсутствует' in s: return 'color: #d32f2f; font-weight: bold;' # Red
        if 'Не совпадает дата' in s: return 'color: #e65100; font-weight: bold;' # Orangeish
        if 'Ошибка' in s: return 'color: #d32f2f; font-weight: bold;' # Red
        if s == 'OK': return 'color: #2e7d32; font-weight: bold;' # Green
        return ''

    def color_none(val): return 'color: #9e9e9e; font-style: italic;' if str(val) == "None" else '' # Grey italic for missing values

    st.header(f"📊 Результаты сверки: {target_month_name} {target_year}")
    
    if not df_main.empty:
        discrepancies = df_main[df_main['Is_Error'] == True]
        
        # Metrics (Humanized labels)
        total_cnt = len(df_main)
        truly_missing = df_main['Status_Exist'].str.contains('Отсутствует').sum()
        date_cutoff = df_main['Status_Exist'].str.contains('Не совпадает дата').sum()
        
        price_cnt = 0
        net_diff = 0.0
        if use_price:
            price_errs = discrepancies[discrepancies['Status_Price'] == 'Ошибка в сумме']
            price_cnt = len(price_errs)
            net_diff = price_errs['Diff'].sum()
        
        content_cnt = 0
        if use_var_a: content_cnt += discrepancies['Status_User'].str.contains('Ошибка').sum()
        if use_var_b: content_cnt += discrepancies[f'Status_{add_field_name}'].str.contains('Ошибка').sum()

        # Display Metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Всего строк (в периоде)", total_cnt)
        m2.metric("❌ Отсутствуют (Вообще)", truly_missing, delta_color="inverse")
        m3.metric("📅 Расхождение дат", date_cutoff, delta_color="off")
        if use_price: m4.metric("Ошибки в сумме", price_cnt, delta=f"Разница: {net_diff:,.2f}")
        else: m4.metric("Ошибки в сумме", "Не проверялось")
        m5.metric("Прочие ошибки", content_cnt, delta_color="inverse")

        # Table Controls
        c_view, c_down = st.columns([1, 3])
        with c_view: show_all = st.checkbox("Показать все строки (включая совпавшие)", value=False)
        
        view_main = df_main.copy() if show_all else discrepancies.copy()
        
        if not view_main.empty:
            view_main['Date_OUR_Str'] = view_main['Date_OUR'].dt.strftime('%d.%m.%Y').fillna("None")
            view_main['Date_PROV_Str'] = view_main['Date_PROV'].dt.strftime('%d.%m.%Y').fillna("None")
            
            # Dynamic Columns with friendly names
            cols = ['ID_OUR', 'ID_PROV', 'Date_OUR_Str', 'Date_PROV_Str']
            renames = {'Date_OUR_Str': 'Дата (Наши)', 'Date_PROV_Str': 'Дата (Партнёр)', 'Status_Exist': 'Статус (Наличие)'}
            
            cols.append('Status_Exist')

            if use_price: 
                cols.extend(['Price_1', 'Price_2', 'Diff', 'Status_Price'])
                renames.update({'Price_1': 'Сумма (Наши)', 'Price_2': 'Сумма (Партнёр)', 'Diff': 'Разница', 'Status_Price': 'Статус (Сумма)'})
            
            if use_var_a: 
                cols.extend(['User_1', 'User_2', 'Status_User'])
                renames.update({'User_1': f"{va_col_1} (Наши)", 'User_2': f"{va_col_2} (Партнёр)", 'Status_User': 'Статус (Текст А)'})
            
            if use_var_b:
                col_stat_dyn = f'Status_{add_field_name}'
                cols.extend(['Add_1', 'Add_2', col_stat_dyn])
                renames.update({'Add_1': f"{vb_col_1} (Наши)", 'Add_2': f"{vb_col_2} (Партнёр)", col_stat_dyn: f'Статус ({add_field_name})'})
            
            with c_down:
                csv_main = view_main[cols].rename(columns=renames).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Скачать полный отчет (CSV)", csv_main, "main_report.csv", "text/csv", type="primary")

            st.dataframe(
                view_main[cols].rename(columns=renames).fillna("None").style.map(color_none).map(color_cells),
                use_container_width=True, hide_index=True
            )
        else:
            if show_all: st.warning("Нет данных для отображения.")
            else: st.success("🎉 Отлично! Расхождений за этот период не найдено.")
    else:
        st.warning(f"В выбранном периоде ({target_month_name} {target_year}) транзакций не найдено.")

    st.divider()

    # Investigation Table (Humanized headers)
    st.header("🕵️ Расследование (Поиск потерянных)")
    st.markdown("Здесь показаны записи, которые не нашлись в выбранном месяце, и результат их поиска по всему файлу.")
    if not df_inv.empty:
        cols_inv = ['ID_OUR', 'ID_PROV', 'Investigation', 'Status_Exist']
        
        df_inv['Date_OUR_Str'] = df_inv['Date_OUR'].dt.strftime('%d.%m.%Y').fillna("Unknown")
        df_inv['Date_PROV_Str'] = df_inv['Date_PROV'].dt.strftime('%d.%m.%Y').fillna("Unknown")
        
        cols_inv.insert(1, 'Date_OUR_Str')
        cols_inv.insert(3, 'Date_PROV_Str')
        
        renames_inv = {
            'ID_OUR': 'ID (Наши)', 'ID_PROV': 'ID (Партнёр)',
            'Date_OUR_Str': 'Дата (Наши)', 'Date_PROV_Str': 'Дата (Партнёр)', 
            'Investigation': 'Результат глобального поиска', 'Status_Exist': 'Исходная проблема'
        }

        def color_res(val):
            if '✅' in str(val): return 'color: #2e7d32; font-weight: bold;'
            if '❌' in str(val): return 'color: #d32f2f; font-weight: bold;'
            return ''

        csv_inv = df_inv[cols_inv].rename(columns=renames_inv).to_csv(index=False).encode('utf-8')
        st.download_button("📥 Скачать результат расследования (CSV)", csv_inv, "investigation_report.csv", "text/csv")

        st.dataframe(df_inv[cols_inv].rename(columns=renames_inv).fillna("None").style.map(color_res, subset=['Результат глобального поиска']), use_container_width=True, hide_index=True)
    else:
        st.success("Расследовать нечего (все записи найдены в целевом месяце).")
elif files_ready:
    # Hint to press the button
    st.info("👆 Настройте параметры выше и нажмите большую кнопку 'Запустить сверку данных'.")
else:
    # Initial state hint
    st.info("👈 Начните с загрузки файлов в Шаге 1.")
