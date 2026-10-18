import os
import telebot
from telebot import apihelper
from telebot.util import smart_split
from llm_service import process_user_message, init_db

# =====================================================================
# 1. АВТО-НАСТРОЙКА ПРОКСИ ДЛЯ ТЕЛЕГРАМА
# =====================================================================
# Если бот запущен на серверах GitHub Actions, прокси не нужен (там всё открыто).
# Если бот запущен локально на вашем ПК, автоматически подключаем туннель v2rayN.
if os.environ.get("GITHUB_ACTIONS") == "true":
    print("Бот запущен в облаке GitHub Actions. Подключение напрямую...")
else:
    print("Бот запущен локально. Подключаем SOCKS5-прокси v2rayN (порт 10808)...")
    apihelper.proxy = {
        'http': 'socks5h://127.0.0.1:10808',
        'https': 'socks5h://127.0.0.1:10808'
    }

# =====================================================================
# 2. ПОЛУЧЕНИЕ ТОКЕНА ТЕЛЕГРАМ С ИСПРАВЛЕННОЙ ЛОГИКОЙ
# =====================================================================
# Сначала пытаемся взять токен из переменных окружения (для GitHub)
BOT_TOKEN = os.environ.get("BOT_API_TOKEN")

# Если переменной нет (локальный запуск), берем токен из файла bot_secrets.py
if not BOT_TOKEN:
    try:
        from bot_secrets import secrets
        BOT_TOKEN = secrets.get("BOT_API_TOKEN")
    except ImportError:
        pass

# Если токен так и не удалось найти, выдаем понятную ошибку
if not BOT_TOKEN:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Токен Telegram (BOT_API_TOKEN) не найден ни в системе, ни в bot_secrets.py!")

# Инициализируем бота строго ПОСЛЕ того, как токен успешно найден
bot = telebot.TeleBot(BOT_TOKEN)

# =====================================================================
# 3. ИНИЦИАЛИЗАЦИЯ И ОБРАБОТЧИКИ КОМАНД
# =====================================================================

# Инициализируем базу данных при старте
init_db()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я твой персональный ИИ-ассистент по уходу за кожей. 🌟\n"
        "Задай мне любой вопрос о подборе косметики, этапах ухода или типах кожи, и я помогу тебе разобраться!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    user_text = message.text

    # Показываем плашку "печатает...", пока Gemini думает над ответом
    bot.send_chat_action(chat_id, action='typing')

    try:
        # Передаем управление в llm_service.py (он запишет всё в Firebase и вернет ответ)
        ai_response = process_user_message(chat_id, user_text)

        # Режем длинные тексты (защита от ошибки MESSAGE_TOO_LONG в Telegram)
        chunks = smart_split(ai_response, chars_per_string=3500)
        for chunk in chunks:
            bot.send_message(chat_id, chunk, parse_mode="Markdown")

    except Exception as e:
        print(f"Ошибка при обработке сообщения в чате {chat_id}: {e}")
        bot.send_message(
            chat_id, 
            "Извини, произошла техническая ошибка при обработке запроса. Пожалуйста, попробуй еще раз чуть позже."
        )

if __name__ == "__main__":
    print("Telegram-бот успешно запущен и слушает сообщения...")
    bot.infinity_polling()
