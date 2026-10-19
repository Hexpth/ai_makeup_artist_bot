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
BTN_RESET_TEXT = "RESET"
# Инициализируем базу данных при старте
init_db()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я твой персональный ИИ-ассистент по уходу за кожей. 🌟\n"
        "Задай мне любой вопрос о подборе косметики, этапах ухода или типах кожи, и я помогу тебе разобраться!"
    )
    bot.reply_to(message, welcome_text)

# --- ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ В BOT.PY ---
@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    text = message.text
    chat_id = message.chat.id

    # 1. Сначала проверяем, не является ли текст нажатием кнопки RESET
    if text == BTN_RESET_TEXT:
        delete_history(chat_id)  # Чистим базу данных напрямую
        bot.send_message(
            chat_id,
            text="✅ История нашего диалога очищена. Можем начать всё с чистого листа!",
            reply_markup=create_main_keyboard()
        )
        return  # 🌟 ВАЖНО: Выходим из функции, чтобы код ниже НЕ выполнялся!

    # 2. Если это не кнопка, проверяем на случайные команды
    if text.startswith('/'):
        bot.reply_to(message, "Пожалуйста, используйте команды без дополнительного текста или просто задайте вопрос.")
        return

    # 3. Если это обычный вопрос к AI
    thinking_message = bot.send_message(chat_id, "💄 Думаю над вашим вопросом...")
    
    # Только здесь вызываем оркестратор для работы с Gemini
    response_text = process_user_message(chat_id, user_question=text)
    
    # Безопасно выводим ответ (с защитой от слишком длинных сообщений)
    try:
        bot.edit_message_text(
            chat_id=chat_id, 
            message_id=thinking_message.message_id, 
            text=response_text,
            parse_mode="Markdown"
        )
    except Exception:
        bot.delete_message(chat_id, thinking_message.message_id)
        bot.send_message(chat_id, response_text, parse_mode="Markdown")


if __name__ == "__main__":
    print("Telegram-бот успешно запущен и слушает сообщения...")
    bot.infinity_polling(timeout=60, long_polling_timeout=5)

