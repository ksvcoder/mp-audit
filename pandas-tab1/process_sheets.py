"""
Скрипт для разбора столбца E и развёртывания данных в Google Sheets.
Преобразует данные так, чтобы каждый вопрос из столбца E был на отдельной строке
с повторением значений из столбцов A-D.
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import re

# ID таблицы из URL
SPREADSHEET_ID = "1x1dP43jdzoEQFBvxTj-HOUUWnchIVBCLhaBInnf1-64"
SOURCE_SHEET = "Данные"  # Название исходного листа (может понадобиться изменить)
RESULT_SHEET = "результат"  # Название листа для результата


def get_google_sheets_client():
    """
    Получить клиент Google Sheets.
    Требует файл credentials.json в текущей папке.
    Получить его можно:
    1. Перейти на https://console.cloud.google.com
    2. Создать сервисный аккаунт
    3. Скачать JSON ключ
    4. Сохранить как credentials.json
    """
    creds = Credentials.from_service_account_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return gspread.authorize(creds)


def read_data_from_sheets(client):
    """Читает данные из исходного листа"""
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    # Получить все листы
    sheets = spreadsheet.worksheets()
    sheet_names = [s.title for s in sheets]
    print(f"Доступные листы: {sheet_names}")

    # Если SOURCE_SHEET не существует, использовать первый лист
    try:
        worksheet = spreadsheet.worksheet(SOURCE_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Лист '{SOURCE_SHEET}' не найден. Используем первый лист.")
        worksheet = spreadsheet.sheet1

    # Читаем все данные
    data = worksheet.get_all_values()

    # Создаём DataFrame (пропускаем заголовок если он есть)
    if data:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df, worksheet
    return None, worksheet


def expand_column_e(df):
    """
    Разбирает столбец с вопросами и развёртывает данные.
    Вопросы разделяются по паттерну: число + точка + пробел (1. , 2. , 3. и т.д.)
    """

    # Найти столбец с вопросами (содержит "Вопрос" в названии или последний полный столбец)
    question_col = None
    for col in df.columns:
        if 'Вопрос' in str(col).lower() or 'вопрос' in str(col):
            question_col = col
            break

    if question_col is None:
        # Если не найден, используем последний столбец (кроме пустых)
        for col in reversed(df.columns):
            if col.strip():
                question_col = col
                break

    if question_col is None:
        raise ValueError("Столбец с вопросами не найден в таблице")

    # Найти столбцы для повторения (первые столбцы)
    repeat_cols = [col for col in df.columns if col != question_col]

    # Создаём список для результатов
    expanded_data = []

    for idx, row in df.iterrows():
        # Получаем значение из столбца с вопросами
        questions_value = str(row[question_col]) if question_col in row and row[question_col] else ''

        if not questions_value or questions_value == 'nan':
            continue

        # Разбираем вопросы по разным разделителям
        questions = []

        # Вариант 1: разделены по новой строке
        if '\n' in questions_value:
            questions = [q.strip() for q in questions_value.split('\n') if q.strip()]
        # Вариант 2: разделены по точке с запятой
        elif ';' in questions_value:
            questions = [q.strip() for q in questions_value.split(';') if q.strip()]
        # Вариант 3: вопросы идут подряд с паттерном "1. ", "2. " и т.д.
        else:
            # Найти все совпадения вида "N. текст вопроса?" где N - число
            matches = re.findall(r'\d+\.\s+[^?]*\?', questions_value)
            if matches:
                questions = [m.strip() for m in matches if m.strip()]
            else:
                # Если вопросительные знаки не найдены, берём всё как один вопрос
                if questions_value:
                    questions = [questions_value.strip()]

        # Для каждого вопроса создаём новую строку с данными родительской строки
        for question in questions:
            new_row = {}
            # Копируем значения из столбцов повторения
            for col in repeat_cols:
                new_row[col] = row[col] if col in row else ''
            # Добавляем вопрос
            new_row[question_col] = question
            expanded_data.append(new_row)

    # Создаём новый DataFrame
    result_df = pd.DataFrame(expanded_data)
    return result_df


def write_results_to_sheets(client, result_df, worksheet):
    """Записывает результаты в лист "результат" """
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    # Пытаемся получить лист результата
    try:
        result_worksheet = spreadsheet.worksheet(RESULT_SHEET)
        # Очищаем существующий лист
        result_worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        # Создаём новый лист если его нет
        result_worksheet = spreadsheet.add_worksheet(RESULT_SHEET, 1000, 10)

    # Записываем данные
    # Сначала заголовки
    headers = result_df.columns.tolist()
    result_worksheet.append_row(headers)

    # Потом данные
    data_to_write = result_df.values.tolist()
    for chunk in [data_to_write[i:i+100] for i in range(0, len(data_to_write), 100)]:
        result_worksheet.append_rows(chunk)

    print(f"Результаты записаны в лист '{RESULT_SHEET}'")
    print(f"Всего строк: {len(result_df)}")


def main():
    """Основная функция"""
    try:
        # Получаем клиент
        print("Подключаемся к Google Sheets...")
        client = get_google_sheets_client()

        # Читаем данные
        print("Читаем данные из таблицы...")
        df, worksheet = read_data_from_sheets(client)

        if df is None or df.empty:
            print("Таблица пуста!")
            return

        print(f"Прочитано {len(df)} строк")
        print(f"Столбцы: {df.columns.tolist()}")
        print("\nПервая строка:")
        print(df.iloc[0])

        # Развёртываем столбец E
        print("\nРазвёртываем столбец E...")
        result_df = expand_column_e(df)

        print(f"После развёртывания: {len(result_df)} строк")

        # Записываем результаты в Google Sheets
        print("\nЗаписываем результаты в Google Sheets...")
        write_results_to_sheets(client, result_df, worksheet)

        print("\n✅ Готово!")

    except FileNotFoundError:
        print("❌ Ошибка: файл credentials.json не найден!")
        print("\nИнструкция по получению credentials.json:")
        print("1. Перейти на https://console.cloud.google.com")
        print("2. Создать новый проект")
        print("3. Включить Google Sheets API")
        print("4. Создать сервисный аккаунт")
        print("5. Скачать JSON ключ")
        print("6. Сохранить как 'credentials.json' в папке скрипта")
        print("7. Поделиться Google таблицей с email сервисного аккаунта")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
