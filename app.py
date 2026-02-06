import streamlit as st
import pandas as pd
import io

# 1. Настройка страницы
st.set_page_config(page_title="Сверка отчетов", layout="wide", page_icon="⚖️")

st.title("⚖️ Инструмент Сверки Данных")
st.markdown("""
**Инструкция:**
1. Загрузите два файла (CSV или Excel).
2. Выберите колонки, по которым искать совпадения (ID).
3. Выберите колонки с суммами.
4. Получите готовый отчет о расхождениях.
""")
st.divider()

# --- ФУНКЦИИ ---
@st.cache_data
def load_data(file):
    """Читает файл CSV или Excel"""
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Ошибка при чтении файла {file.name}: {e}")
        return None

def clean_currency(series):
    """Очистка денежных форматов (убирает пробелы, $, руб и т.д.)"""
    if pd.api.types.is_numeric_dtype(series):
        return series
    return series.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.').astype(float)

# --- ИНТЕРФЕЙС: ЗАГРУЗКА ---
col1, col2 = st.columns(2)
with col1:
    f1 = st.file_uploader("📂 Файл 1 (Эталон/Наши данные)", key="f1")
with col2:
    f2 = st.file_uploader("📂 Файл 2 (Сверка/Провайдер)", key="f2")

# --- ОСНОВНАЯ ЛОГИКА ---
if f1 and f2:
    df1 = load_data(f1)
    df2 = load_data(f2)

    if df1 is not None and df2 is not None:
        st.success("Файлы загружены. Настройте колонки ниже.")
        st.write("---")

        # Выбор колонок
        c1, c2, c3, c4 = st.columns(4)
        
        # ID
        with c1:
            id_1 = st.selectbox("ID в Файле 1", df1.columns)
        with c2:
            id_2 = st.selectbox("ID в Файле 2", df2.columns)
            
        # Суммы (Автопоиск 'amount' или 'sum')
        def get_idx(cols):
            for i, c in enumerate(cols):
                if 'sum' in c.lower() or 'amount' in c.lower(): return i
            return 0

        with c3:
            sum_1 = st.selectbox("Сумма в Файле 1", df1.columns, index=get_idx(df1.columns))
        with c4:
            sum_2 = st.selectbox("Сумма в Файле 2", df2.columns, index=get_idx(df2.columns))

        # Кнопка запуска
        if st.button("🚀 Сравнить таблицы", type="primary"):
            
            # 1. Подготовка ключей (все в строку, убираем пробелы)
            df1['_key'] = df1[id_1].astype(str).str.strip()
            df2['_key'] = df2[id_2].astype(str).str.strip()

            # 2. Подготовка сумм
            df1['_val'] = clean_currency(df1[sum_1])
            df2['_val'] = clean_currency(df2[sum_2])

            # 3. Объединение (Full Outer Join)
            merged = pd.merge(
                df1[[id_1, sum_1, '_key', '_val']], 
                df2[[id_2, sum_2, '_key', '_val']], 
                on='_key', 
                how='outer', 
                suffixes=('_1', '_2'),
                indicator=True
            )

            # 4. Расчет разницы
            merged['Сумма_1'] = merged['_val_1'].fillna(0)
            merged['Сумма_2'] = merged['_val_2'].fillna(0)
            merged['Разница'] = (merged['Сумма_1'] - merged['Сумма_2']).round(2)

            # 5. Статусы
            def set_status(row):
                if row['_merge'] == 'left_only': return 'Нет во 2-м файле'
                if row['_merge'] == 'right_only': return 'Нет в 1-м файле'
                if row['Разница'] != 0: return 'Несовпадение сумм'
                return 'OK'
            
            merged['Статус'] = merged.apply(set_status, axis=1)

            # 6. Фильтрация
            errors = merged[merged['Статус'] != 'OK'].copy()

            # --- РЕЗУЛЬТАТЫ ---
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Всего строк", len(merged))
            m2.metric("С ошибками", len(errors), delta_color="inverse")
            m3.metric("Сумма расхождений", f"{errors['Разница'].sum():,.2f}")

            if not errors.empty:
                st.subheader("⚠️ Найденные расхождения")
                
                # Показываем только полезные колонки
                show_cols = ['_key', 'Сумма_1', 'Сумма_2', 'Разница', 'Статус']
                
                # Красим таблицу
                def color_rows(val):
                    color = '#ffebee' if val != 'OK' else '#e8f5e9'
                    return f'background-color: {color}'

                st.dataframe(errors[show_cols].style.applymap(color_rows, subset=['Статус']), use_container_width=True)

                # Скачивание
                csv = errors.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Скачать отчет (CSV)",
                    csv,
                    "reconcile_report.csv",
                    "text/csv",
                    type="primary"
                )
            else:
                st.balloons()
                st.success("Идеальное совпадение! Расхождений нет.")
