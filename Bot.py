import os
import telebot
from telebot import apihelper
from telebot.util import smart_split
from llm_service import process_user_message, init_db


BOT_TOKEN = os.environ.get("BOT_API_TOKEN")
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
