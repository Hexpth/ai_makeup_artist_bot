from telebot import types
from secrets import secrets
import telebot
import os

# --- Импортируем функции из нашего нового сервиса ---
from llm_service import process_user_message, delete_history, init_db






# --- Инициализация ---
try:
    BOT_TOKEN = secrets.get('BOT_API_TOKEN') # токен 
    if not BOT_TOKEN:
        raise ValueError("Токен бота не найден. Установите переменную окружения BOT_API_TOKEN.")
    bot = telebot.TeleBot(BOT_TOKEN)
except (ValueError) as e:
    print(e)
    exit()

# --- Константа для кнопки ---
BTN_RESET_TEXT = "RESET"

# --- Клавиатура ---
def create_main_keyboard():
    """Создает основную клавиатуру с кнопкой сброса."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_reset = types.KeyboardButton(BTN_RESET_TEXT)
    markup.add(btn_reset)
    return markup

# --- Обработчики команд ---

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
    bot.reply_to(message, "✅ История нашего диалога очищена. Можем начать всё с чистого листа!")


# --- ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ---
@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    """
    Обрабатывает все текстовые сообщения: и нажатия кнопок, и обычные вопросы.
    """
    text = message.text
    chat_id = message.chat.id

    # 1. Сначала проверяем, не является ли текст нажатием кнопки
    if text == BTN_RESET_TEXT:
        delete_history(chat_id)
        bot.send_message(
            chat_id,
            text="✅ История нашего диалога очищена. Можем начать всё с чистого листа!",
            reply_markup=create_main_keyboard()
        )
    # 2. Если это не кнопка, значит, это вопрос к AI
    else:
        # Игнорируем команды, если они случайно попали сюда
        if text.startswith('/'):
            bot.reply_to(message, "Пожалуйста, используйте команды без дополнительного текста или просто задайте вопрос.")
            return

        # Отправляем сообщение о том, что мы думаем
        thinking_message = bot.send_message(chat_id, "💄 Думаю над вашим вопросом...")
        
        # Вызываем наш "микросервис" для получения ответа
        response_text = process_user_message(chat_id, user_question=text)
        
        # Редактируем сообщение "Думаю..." и показываем финальный ответ
        bot.edit_message_text(
            chat_id=chat_id, 
            message_id=thinking_message.message_id, 
            text=response_text
        )

# Старые обработчики `handle_text` и `handle_text_buttons` были объединены 
# в один `handle_all_text` выше, поэтому их нужно удалить.


# --- Запуск бота ---
if __name__ == '__main__':
    # При старте бота один раз инициализируем базу данных
    init_db()
    
    print("Бот-визажист запущен и подключен к базе данных...")
    bot.polling(none_stop=True, interval=0)

