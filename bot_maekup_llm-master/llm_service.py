import os
import psycopg2
from huggingface_hub import InferenceClient
from secrets import secrets
# --- 1. Настройки ---

# ID модели на Hugging Face, которую будем использовать
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# Получаем токен Hugging Face из переменных окружения
HF_API_KEY = secrets.get("HF_TOKEN")

# --- Настройки подключения к вашей базе данных PostgreSQL ---
# Эти данные соответствуют вашей команде `docker run`
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "mysecretpassword"
DB_HOST = "localhost" # Docker и бот на одной машине
DB_PORT = "5433" # Внешний порт, который вы указали

# Системный промпт, задающий роль и поведение модели
SYSTEM_PROMPT = "Ты — «Виртуальный визажист», дружелюбный и эмпатичный эксперт по косметике. Твоя задача — проанализировать запрос клиента, понять его проблему и предложить подходящие типы косметических средств, давая полезные советы. Всегда отвечай на русском языке."

# --- 2. Функции для работы с базой данных ---

def get_db_connection():
    """Устанавливает и возвращает соединение с базой данных."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Ошибка подключения к базе данных: {e}")
        print("Убедитесь, что Docker-контейнер с PostgreSQL запущен и доступен по указанным хосту и порту.")
        return None

def init_db():
    """Создает таблицу для истории чатов, если она еще не создана."""
    conn = get_db_connection()
    if conn is None:
        return
    
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                role VARCHAR(10) NOT NULL, -- 'user' или 'assistant'
                content TEXT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")

def save_message(chat_id, role, content):
    """Сохраняет одно сообщение в базу данных."""
    conn = get_db_connection()
    if conn is None:
        return

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO chat_history (chat_id, role, content) VALUES (%s, %s, %s)",
            (chat_id, role, content)
        )
    conn.commit()
    conn.close()

def get_history(chat_id):
    """Извлекает историю диалога для указанного chat_id из базы данных."""
    conn = get_db_connection()
    if conn is None:
        return []

    with conn.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM chat_history WHERE chat_id = %s ORDER BY timestamp ASC",
            (chat_id,)
        )
        history = [{"role": role, "content": content} for role, content in cur.fetchall()]
    conn.close()
    return history

def delete_history(chat_id):
    """Удаляет историю диалога для указанного chat_id."""
    conn = get_db_connection()
    if conn is None:
        return

    with conn.cursor() as cur:
        cur.execute("DELETE FROM chat_history WHERE chat_id = %s", (chat_id,))
    conn.commit()
    conn.close()


# --- 3. Функция для работы с LLM ---

def _call_huggingface_api(chat_history):
    """Приватная функция для вызова модели с готовой историей."""
    if not HF_API_KEY:
        return "Ошибка: Токен Hugging Face (HF_TOKEN) не найден в переменных окружения."
        
    try:
        client = InferenceClient(model=MODEL_ID, token=HF_API_KEY)
        response = client.chat_completion(
            messages=chat_history,
            max_tokens=1500,
            stream=False,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при обращении к Hugging Face API: {e}")
        return "К сожалению, произошла техническая неполадка при обращении к AI-модели. Пожалуйста, попробуйте снова через минуту."

# --- 4. Главная функция-оркестратор ---

def process_user_message(chat_id, user_question):
    """
    Основная логика: сохраняет вопрос, получает историю, вызывает LLM, 
    сохраняет ответ и возвращает его пользователю.
    """
    # 1. Сохраняем новое сообщение пользователя в БД
    save_message(chat_id, 'user', user_question)

    # 2. Получаем всю историю диалога из БД
    history = get_history(chat_id)

    # 3. Добавляем системный промпт в начало истории для каждого запроса
    messages_for_llm = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 4. Вызываем языковую модель
    assistant_response = _call_huggingface_api(messages_for_llm)

    # 5. Сохраняем ответ модели в БД, чтобы учесть его в следующем запросе
    save_message(chat_id, 'assistant', assistant_response)

    # 6. Возвращаем ответ для отправки в Telegram
    return assistant_response


