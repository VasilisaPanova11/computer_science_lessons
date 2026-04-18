# Геймификация уроков информатики

Веб-приложение для геймификации подготовки школьников к ЕГЭ по информатике.  
Стек: Python 3.11 · Django 4.2 · PostgreSQL 15 · HTML5/CSS3/Vanilla JS

## Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone https://github.com/VasilisaPanova11/computer_science_lessons.git
cd computer_science_lessons
```

### 2. Создать виртуальное окружение и установить зависимости
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настроить переменные окружения
Создать файл `.env` в корне проекта:
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=cs_lessons
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

### 4. Применить миграции
```bash
python manage.py migrate
```

### 5. Заполнить БД тестовыми данными
```bash
python manage.py seed_data
```
Создаёт: 1 администратора, 1 учителя, 3 ученика, 1 класс, 1 тему, 4 задания типа math_path.

### 6. Запустить сервер
```bash
python manage.py runserver
```
Приложение доступно по адресу: http://127.0.0.1:8000/
