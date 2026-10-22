import os
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

# =====================================================================
# 1. СМАРТ-ПОЛУЧЕНИЕ ТОКЕНА GEMINI (ДЛЯ ОБЛАКА И ЛОКАЛЬНО)
# =====================================================================
API_KEY = os.environ.get("GEM_TOKEN")

if not API_KEY:
    try:
        from bot_secrets import secrets
        API_KEY = secrets.get("GEM_TOKEN")
    except ImportError:
        pass

MODEL_ID = "gemini-3.5-flash-lite"  

if API_KEY:
    ai_client = genai.Client(api_key=API_KEY)
else:
    print("ВНИМАНИЕ: Ключ GEM_TOKEN не найден ни в системе, ни в bot_secrets!")
    ai_client = None

# =====================================================================
# 2. ПОДКЛЮЧЕНИЕ К ОБЛАКУ FIREBASE FIRESTORE
# =====================================================================
try:
    if not os.path.exists("firebase_key.json") and os.environ.get("FIREBASE_KEY_CONTENT"):
        with open("firebase_key.json", "w", encoding="utf-8") as f:
            f.write(os.environ.get("FIREBASE_KEY_CONTENT"))

    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Firestore успешно подключена.")
except Exception as e:
    print(f"Ошибка инициализации Firebase: {e}")
    db = None

# Чтение системного промпта
try:
    with open("./system_prompt.txt", mode='r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    print("ВНИМАНИЕ: Файл system_prompt.txt не найден!")
    SYSTEM_PROMPT = "Ты — полезный ИИ-ассистент, эксперт по макияжу и визажу."

# =====================================================================
# 3. ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ
# =====================================================================

def init_db():
    print("База данных Firebase Firestore готова к работе.")

def save_message(chat_id, role, content):
    if db is None:
        return
    try:
        user_ref = db.collection("chathistory").document(str(chat_id))
        user_ref.collection("messages").add({
            "role": role,          # 'user' или 'assistant'
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Ошибка сохранения сообщения: {e}")

def get_history(chat_id):
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
        print(f"Ошибка получения истории: {e}")
        return []

def delete_history(chat_id):
    if db is None:
        return
    try:
        messages_ref = db.collection("chathistory").document(str(chat_id)).collection("messages")
        docs = messages_ref.stream()
        for doc in docs:
            doc.reference.delete()
        print(f"История чата {chat_id} успешно очищена.")
    except Exception as e:
        print(f"Ошибка удаления истории: {e}")

# =====================================================================
# 4. ФУНКЦИИ ДЛЯ ОБРАБОТКИ ЗАПРОСОВ К GEMINI
# =====================================================================

def _call_gemini_api(db_history, current_image_bytes=None):
    """Внутренняя функция для вызова Gemini с историей и текущим фото."""
    if not ai_client:
        return "Ошибка: Токен Gemini (GEM_TOKEN) не найден."
        
    try:
        gemini_contents = []
        
        # Переносим историю переписки в формат Gemini (только текст)
        for msg in db_history:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
        # Если к текущему запросу приложена картинка, мы ОБЯЗАНЫ передать её 
        # в самом последнем элементе контента в виде Blob-структуры рядом с текстом.
        if current_image_bytes and gemini_contents and gemini_contents[-1].role == "user":
            # Берем последнее сообщение пользователя из истории, которое мы только что сохранили,
            # и добавляем к его текстовой части бинарную часть с фото.
            user_text_part = gemini_contents[-1].parts[0]
            photo_part = types.Part.from_bytes(data=current_image_bytes, mime_type='image/jpeg')
            
            # Перезаписываем parts для последнего сообщения, делая его мультимодальным
            gemini_contents[-1].parts = [photo_part, user_text_part]

        # Делаем запрос к ИИ
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
        return "К сожалению, возникла техническая неполадка. Пожалуйста, попробуйте снова."

def process_user_message(chat_id, user_question, image_bytes=None):
    """Главный оркестратор: сохраняет текстовый промпт, подтягивает историю, передает байты фото."""
    # В историю пишем только текст, чтобы не раздувать БД бинарниками
    save_message(chat_id, 'user', user_question)
    
    # Получаем историю (куда уже вошел наш свежий вопрос)
    history = get_history(chat_id)
    
    # Передаем и историю, и «сырые» байты картинки для анализа
    assistant_response = _call_gemini_api(history, current_image_bytes=image_bytes)
    
    save_message(chat_id, 'assistant', assistant_response)
    return assistant_response
