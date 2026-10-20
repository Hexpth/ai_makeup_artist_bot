import os
import telebot
from telebot import types
from llm_service import process_user_message, delete_history, init_db

# --- Initialization ---
try:
    # First look up GitHub Secrets, then fallback to local file
    BOT_TOKEN = os.environ.get("BOT_API_TOKEN")
    
    if not BOT_TOKEN:
        try:
            from secrets import secrets
            BOT_TOKEN = secrets.get('BOT_API_TOKEN')
        except ImportError:
            pass
            
    if not BOT_TOKEN:
        raise ValueError("Токен бота не найден. Установите переменную окружения BOT_API_TOKEN.")
        
    bot = telebot.TeleBot(BOT_TOKEN)
except ValueError as e:
    print(e)
    exit()

# --- Keyboard Setup (Must be defined BEFORE handlers use it!) ---
BTN_RESET_TEXT = "RESET"

def create_main_keyboard():
    """Создает основную клавиатуру с кнопкой сброса."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_reset = types.KeyboardButton(BTN_RESET_TEXT)
    markup.add(btn_reset)
    return markup

# --- Command Handlers ---

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    """Обработчик команд /start и /help."""
    bot.send_message(
        message.chat.id,
        text=(
            f"Привет, {message.from_user.first_name}! 🖖🏻\n"
            "Я ваш личный виртуальный визажист на базе AI.\n\n"
            "Задайте мне любой вопрос о макияже, и я постараюсь помочь.\n"
            "Например: `Посоветуй, как скрыть темные круги под глазами.`\n\n"
            "Чтобы начать диалог заново, используйте команду /reset или нажмите кнопку RESET."
        ),
        reply_markup=create_main_keyboard(),
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['reset'])
def reset_history_command(message):
    """Сбрасывает историю диалога по команде /reset."""
    chat_id = message.chat.id
    delete_history(chat_id)
    bot.reply_to(
        message, 
        "✅ История нашего диалога очищена. Можем начать всё с чистого листа!",
        reply_markup=create_main_keyboard()
    )

# --- Main Message Handler for Text and Buttons ---
@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    text = message.text
    chat_id = message.chat.id

    # 1. Intercept the RESET button click immediately
    if text == BTN_RESET_TEXT:
        delete_history(chat_id)
        bot.send_message(
            chat_id,
            text="✅ История нашего диалога очищена. Можем начать всё с чистого листа!",
            reply_markup=create_main_keyboard()
        )
        return  # Exit early so it doesn't pass "RESET" text to Gemini!

    # 2. Ignore stray commands handled above
    if text.startswith('/'):
        bot.reply_to(message, "Пожалуйста, используйте команды без дополнительного текста или просто задайте вопрос.")
        return

    # 3. Process normal questions through Gemini
    thinking_message = bot.send_message(chat_id, "💄 Думаю над вашим вопросом...")
    response_text = process_user_message(chat_id, user_question=text)
    
    # Securely edit or send message to avoid length crashes
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

# --- Bot Runtime Execution ---
if __name__ == '__main__':
    init_db()
    print("Бот-визажист успешно запущен и слушает сообщения...")
    while True:
        try:
            # Увеличиваем таймауты, чтобы реже моргала сеть
            bot.infinity_polling(timeout=90, long_polling_timeout=10)
        except Exception as e:
            print(f"Критическая ошибка пуллинга: {e}")
            print("Перезапуск соединения с Telegram через 5 секунд...")
            time.sleep(5)
