import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# Конфиг страницы
st.set_page_config(page_title="IT Audit Checklist", layout="wide")

# Заголовок
st.title("📋 IT Audit Checklist")

# Инициализация сессии
if 'current_question_idx' not in st.session_state:
    st.session_state.current_question_idx = 0
if 'answers' not in st.session_state:
    st.session_state.answers = []
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

# ============ ФУНКЦИИ ============

@st.cache_resource
def get_google_sheets_client():
    """Подключение к Google Sheets"""
    try:
        # Для Streamlit Cloud - читаем из Secrets
        if hasattr(st, 'secrets') and len(st.secrets) > 0:
            # Преобразуем Secrets в словарь
            secrets_dict = dict(st.secrets)

            # Если Secrets содержит nested dict gcp_service_account
            if "gcp_service_account" in secrets_dict:
                secrets = dict(st.secrets["gcp_service_account"])
            else:
                # Иначе берём весь Secrets как credentials
                secrets = secrets_dict

            creds = Credentials.from_service_account_info(
                secrets,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return gspread.authorize(creds)
    except Exception as e:
        st.warning(f"⚠️ Не удалось использовать Streamlit Secrets: {e}")

    # Fallback для локального развертывания - читаем файл
    try:
        with open("credentials.json") as f:
            secrets = json.load(f)
        creds = Credentials.from_service_account_info(
            secrets,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return gspread.authorize(creds)
    except FileNotFoundError:
        st.error("❌ Файл credentials.json не найден и Secrets не настроены!")
        st.info("📝 Для Streamlit Cloud: добавьте credentials в Settings → Secrets")
        return None


@st.cache_data
def load_questions():
    """Загружает вопросы из Google Sheet (только Приоритет 1)"""
    try:
        client = get_google_sheets_client()
        if not client:
            return None

        SPREADSHEET_ID = "1x1dP43jdzoEQFBvxTj-HOUUWnchIVBCLhaBInnf1-64"
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet("результат")
        data = worksheet.get_all_values()

        df = pd.DataFrame(data[1:], columns=data[0])

        # Фильтруем только Приоритет 1
        df = df[df['Приоритет'] == 'Приоритет 1 (Фундамент и выживание)']

        return df
    except Exception as e:
        st.error(f"❌ Ошибка при загрузке данных: {e}")
        return None


def save_answer(client, user_name, area, standard, question, answer, fact, comment):
    """Сохраняет ответ в Google Sheet"""
    try:
        SPREADSHEET_ID = "1x1dP43jdzoEQFBvxTj-HOUUWnchIVBCLhaBInnf1-64"
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # Пытаемся получить лист "ответы"
        try:
            worksheet = spreadsheet.worksheet("ответы")
        except gspread.exceptions.WorksheetNotFound:
            # Создаём новый лист если его нет
            worksheet = spreadsheet.add_worksheet("ответы", 1000, 10)
            # Добавляем заголовки
            headers = ["Дата", "ФИ", "Область", "Стандарт", "Вопрос", "Ответ", "Факт", "Комментарий"]
            worksheet.append_row(headers)

        # Добавляем ответ
        row_data = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            user_name,
            area,
            standard,
            question,
            answer,
            fact,
            comment
        ]
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"❌ Ошибка при сохранении: {e}")
        return False


# ============ ОСНОВНОЙ КОД ============

# Загружаем данные
df = load_questions()

if df is None or df.empty:
    st.error("❌ Не удалось загрузить вопросы из таблицы")
    st.stop()

# ---- ВВОДИМ ИМЯ ПОЛЬЗОВАТЕЛЯ ----
if not st.session_state.user_name:
    st.info("👤 Сначала укажите ваше имя")
    name = st.text_input("Ваше ФИ:", key="name_input")
    if name:
        st.session_state.user_name = name
        st.rerun()
else:
    st.success(f"✅ Вы вошли как: **{st.session_state.user_name}**")
    if st.button("🔄 Переключить пользователя"):
        st.session_state.user_name = ""
        st.rerun()

st.divider()

# ---- ФОРМА С ВОПРОСАМИ ----
if st.session_state.user_name:
    # Получаем текущий вопрос
    current_idx = st.session_state.current_question_idx

    if current_idx < len(df):
        current_row = df.iloc[current_idx]
        area = current_row["Область"]
        standard = current_row["Стандарт"]
        question = current_row["Вопрос из чек-листа (что выяснить)"]

        # Показываем прогресс
        progress = (current_idx + 1) / len(df)
        st.progress(progress)
        st.caption(f"Вопрос {current_idx + 1} из {len(df)}")

        # Показываем контекст
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Область:** {area}")
        with col2:
            st.markdown(f"**Стандарт:** {standard}")

        st.divider()

        # Показываем вопрос
        st.markdown(f"### ❓ {question}")

        st.divider()

        # Форма ответа
        col1, col2, col3 = st.columns(3)
        with col1:
            answer = st.radio("Ваш ответ:", ["Да", "Нет", "Частично"], key=f"answer_{current_idx}")

        # Условное отображение полей
        fact = ""
        comment = ""

        if answer in ["Да", "Частично"]:
            st.info("📎 Приложите факт/доказательство (ссылка, файл или описание)")
            fact = st.text_area(
                "Факт/ссылка/описание документа:",
                key=f"fact_{current_idx}",
                height=100
            )

        st.info("💬 Дополнительный комментарий (опционально)")
        comment = st.text_area(
            "Комментарий:",
            key=f"comment_{current_idx}",
            height=80
        )

        st.divider()

        # Кнопки навигации
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("⬅️ Назад", disabled=(current_idx == 0)):
                st.session_state.current_question_idx -= 1
                st.rerun()

        with col2:
            if st.button("✅ Сохранить и далее"):
                # Сохраняем ответ
                client = get_google_sheets_client()
                if client:
                    success = save_answer(
                        client,
                        st.session_state.user_name,
                        area,
                        standard,
                        question,
                        answer,
                        fact,
                        comment
                    )

                    if success:
                        st.success("✅ Ответ сохранён!")

                        # Переходим к следующему вопросу
                        if current_idx + 1 < len(df):
                            st.session_state.current_question_idx += 1
                            st.rerun()
                        else:
                            st.balloons()
                            st.success("🎉 Спасибо! Все вопросы заполнены!")

        with col3:
            if st.button("⏭️ Пропустить"):
                if current_idx + 1 < len(df):
                    st.session_state.current_question_idx += 1
                    st.rerun()

    else:
        st.balloons()
        st.success("🎉 Спасибо за заполнение аудита!")
        st.info(f"✅ Всего заполнено вопросов: {len(df)}")

        if st.button("🔄 Начать заново"):
            st.session_state.current_question_idx = 0
            st.session_state.user_name = ""
            st.rerun()

# ---- БОКОВАЯ ПАНЕЛЬ ----
with st.sidebar:
    st.markdown("### 📊 Статистика")
    total = len(df)
    current = st.session_state.current_question_idx + 1
    st.metric("Текущий вопрос", f"{current}/{total}")

    st.markdown("### 📋 Информация")
    st.markdown("""
    **Приоритет 1:** Фундамент и выживание

    Форма для сбора ответов:
    - 🔘 Варианты: Да / Нет / Частично
    - 📎 При Да/Частично: приложить факты
    - 💬 Опционально: комментарии
    """)
