
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

# =====================================================================
# 1. НАСТРОЙКИ КЛИЕНТА GEMINI
# =====================================================================
API_KEY = secrets.get("GEM_TOKEN")
MODEL_ID = "gemini-3.5-flash-lite"  

if API_KEY:
    # Теперь клиент создается стандартно, он автоматически пойдет через os.environ
    ai_client = genai.Client(api_key=API_KEY)
else:
    print("ВНИМАНИЕ: Ключ GEM_TOKEN не найден в bot_secrets!")
    ai_client = None

# =====================================================================
# 2. ПОДКЛЮЧЕНИЕ К ОБЛАКУ FIREBASE FIRESTORE
# =====================================================================
try:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Firestore успешно подключена.")
except Exception as e:
    print(f"Ошибка инициализации Firebase: {e}")
    db = None

with open("./system_prompt.txt", mode='r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()


# =====================================================================
# 3. ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ
# =====================================================================

def init_db():
    """В Cloud Firestore структура создается динамически при записи."""
    print("База данных Firebase Firestore готова к работе.")

def save_message(chat_id, role, content):
    """Сохраняет сообщение в облачную базу данных Firestore."""
    if db is None:
        print("Ошибка: Нет подключения к Firebase.")
        return

    try:
        user_ref = db.collection("chathistory").document(str(chat_id))
        user_ref.collection("messages").add({
            "role": role,          # 'user' или 'assistant'
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Ошибка сохранения сообщения in Firebase: {e}")

def get_history(chat_id):
    """Извлекает сообщения чата и сортирует их локально (без требования индексов Firestore)."""
    if db is None:
        return []

    try:
        messages_ref = db.collection("chathistory").document(str(chat_id)).collection("messages")
        docs = messages_ref.stream()
        
        raw_history = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("timestamp"):
                raw_history.append(data)
        
        raw_history.sort(key=lambda x: x["timestamp"])
        sorted_history = raw_history[-20:]
        
        history = []
        for msg in sorted_history:
            history.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
        return history
    except Exception as e:
        print(f"Ошибка получения истории из Firebase: {e}")
        return []

def delete_history(chat_id):
    """Удаляет историю диалога для указанного chat_id из Firestore."""
    if db is None:
        return

    try:
        messages_ref = db.collection("chathistory").document(str(chat_id)).collection("messages")
        docs = messages_ref.stream()
        for doc in docs:
            doc.reference.delete()
        print(f"История чата {chat_id} успешно очищена в Firebase.")
    except Exception as e:
        print(f"Ошибка удаления истории в Firebase: {e}")

# =====================================================================
# 4. ФУНКЦИИ ДЛЯ ОБРАБОТКИ ЗАПРОСОВ К GEMINI
# =====================================================================

def _call_gemini_api(db_history):
    """Внутренняя функция для вызова модели Gemini с форматированием истории."""
    if not ai_client:
        return "Ошибка: Токен Gemini (GEM_TOKEN) не найден в bot_secrets."
        
    try:
        gemini_contents = []
        for msg in db_history:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT  
            )
        )
        return response.text
    except Exception as e:
        print(f"Ошибка при обращении к Gemini API: {e}")
        return "К сожалению, возникла техническая неполадка. Пожалуйста, попробуйте снова через минуту."

def process_user_message(chat_id, user_question):
    """Главный оркестратор: сохраняет вопрос, подтягивает историю, получает и сохраняет ответ."""
    save_message(chat_id, 'user', user_question)
    history = get_history(chat_id)
    assistant_response = _call_gemini_api(history)
    save_message(chat_id, 'assistant', assistant_response)
    return assistant_response
