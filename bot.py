from datetime import date, timedelta
import telebot
from telegram_bot_calendar import DetailedTelegramCalendar, WMonthTelegramCalendar
from telebot import types
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
import config
import re

# === CONFIGURATION ===


TOKEN = config.TOKEN
GROUP_CHAT_ID = config.chat_id

bot = telebot.TeleBot(TOKEN)
# Хранилище сессий пользователей
user_sessions = {}


def get_user_data(user_id):
    """Получает или создает данные пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'current_car_id': 0,
            'chat_id': 0,
            'username': f"user_{user_id}",
            'notes_data': {},
            'editing_note_id': None,
            'editing_note_text': None,
            'appointment': {'problem': '', 'vin': '', 'parts': 0, 'time': '', 'date': ''}
        }
    return user_sessions[user_id]


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    user_data['username'] = username
    user_data['chat_id'] = message.chat.id
    show_second_menu(user_data['chat_id'], user_id)


def show_second_menu(chat_id, user_id):
    user_data = get_user_data(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)

    btn_set_id = types.InlineKeyboardButton(
        text="Записаться",
        callback_data="command:/sign_up"
    )
    btn_add_note = types.InlineKeyboardButton(
        text="Изменить данные",
        callback_data="command:/change_data"
    )

    markup.add(btn_set_id, btn_add_note)
    bot.send_message(
        chat_id,
        "🤖 <b>Главное меню</b>\n\n",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('command:'))
def handle_command_callback(call):
    user_id = call.message.from_user.id
    user_data = get_user_data(user_id)
    chat_id = call.message.chat.id
    user_data['chat_id'] = chat_id

    command = call.data.split(':')[1]

    class MockMessage:
        def __init__(self, chat_id, text, user_id):
            self.chat = type('Chat', (), {'id': chat_id})()
            self.text = text
            self.from_user = type('User', (), {'id': user_id})()

    mock_message = MockMessage(chat_id, command, user_id)
    if command == '/set_time':
        set_time(mock_message)
    if command == '/set_problem':
        set_problem(mock_message)
    if command == '/set_vin':
        set_vin(mock_message)
    if command == '/sign_up':
        sign_up(mock_message)
    if command == '/set_parts':
        set_problem(mock_message)

    bot.answer_callback_query(call.id, f"Выполняется: {command}")

@bot.callback_query_handler(func=lambda call: call.data == 'change_data')
def change_data(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    markup = types.InlineKeyboardMarkup(row_width=1)

    btn_change_time = types.InlineKeyboardButton(
        text="изменить дату и время",
        callback_data="command:/change_time"
    )
    btn_change_vin = types.InlineKeyboardButton(
        text="Изменить VIN",
        callback_data="command:/change_vin"
    )
    btn_change_problem = types.InlineKeyboardButton(
        text="Изменить проблему",
        callback_data="command:/change_problem"
    )
    btn_change_parts = types.InlineKeyboardButton(
        text="Изменить заказ запчастей",
        callback_data="command:/change_parts"
    )

    markup.add(btn_change_parts, btn_change_time, btn_change_problem, btn_change_vin)
    bot.send_message(
        user_data['chat_id'],
        "🤖 <b>Выберите параметр для изменения</b>\n\n",
        parse_mode='HTML',
        reply_markup=markup
    )
    # bot.register_next_step_handler(message, lambda m: add_note_to_car(m, user_id))


@bot.callback_query_handler(func=lambda call: call.data == '/sign_up')
def sign_up(message):
    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(message.chat.id, f"Выберите дату", reply_markup=calendar)


@bot.callback_query_handler(func=DetailedTelegramCalendar.func())
def handle_calendar(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    result, key, step = DetailedTelegramCalendar(min_date=min_date, max_date=max_date).process(call.data)

    if not result and key:
        bot.edit_message_text(f"Выберите дату", user_data['chat_id'], call.message.message_id, reply_markup=key)
    elif result:
        user_data['date'] = str(result).replace('-', '.')
        bot.edit_message_text(f"Вы выбрали: {result}", user_data['chat_id'], call.message.message_id)
        times = (10, 11, 12, 13, 14, 15, 16, 17, 18)
        markup = types.InlineKeyboardMarkup(row_width=1)

        for time in times:
            btn_car = types.InlineKeyboardButton(text=f"{time}:00", callback_data=f'time!{time}')
            markup.add(btn_car)

        if len(times) != 0:
            bot.send_message(call.message.chat.id,
                             f"Выберите время", reply_markup=markup)

        else:
            bot.send_message(call.message.chat.id, f"В этот день нет свободных дат, пожалуйста, выберите другую дату")
            bot.register_next_step_handler(call.message, sign_up)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time!'))
def handle_time(call):
    data = call.data.split('!')
    time = int(data[1])
    user_id = call.from_user.id
    print(time)
    user_data = get_user_data(user_id)

    # ✅ Всё прошло: сохраняем время и переходим к VIN
    user_data['time'] = time
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Пропустить"))
    bot.send_message(call.message.chat.id, "Введите VIN или нажмите Пропустить", reply_markup=markup)
    bot.register_next_step_handler(call.message, set_vin)


# обработчик изменение данных


def set_time(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    time_text = message.text.strip()

    # Инициализируем словарь для данных записи, если его еще нет
    if 'appointment' not in user_data:
        user_data['appointment'] = {}

    # 1. Проверка формата времени (только hh:00)
    if not re.match(r"^(0\d|1\d|2[0-3]):00$", time_text):
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите время в формате hh:00 из предложенных вариантов.")
        resend_time_options(message.chat.id, user_data)
        return  # ⛔ НЕ продолжать дальше

    # 2. Проверка, есть ли выбранное время среди доступных
    available_times = set()

    available_times_formatted = {f"{t:02d}:00" for t in available_times}

    if time_text not in available_times_formatted:
        bot.send_message(message.chat.id, "⛔ Это время недоступно. Пожалуйста, выберите доступное время из списка ниже.")
        resend_time_options(message.chat.id, user_data)
        return  # ⛔ НЕ продолжать дальше

    # ✅ Всё прошло: сохраняем время и переходим к VIN
    user_data['time'] = time_text
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Пропустить"))
    bot.send_message(message.chat.id, "Введите VIN или нажмите Пропустить", reply_markup=markup)


def resend_time_options(chat_id, user):
    """Показать доступные часы пользователю заново"""
    times = set()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for time in sorted(times):
        markup.add(types.KeyboardButton(f"{time:02d}:00")).row()
    bot.send_message(chat_id, "Выберите время", reply_markup=markup)


def set_vin(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    # Обработка кнопки "Пропустить"
    if message.text.strip().lower() == "пропустить":
        user_data['appointment']['vin'] = "не указан"
        print(user_id, 'vin', user_data['appointment'])
    else:
        user_data['appointment']['vin'] = message.text
        print(user_id, 'vin', user_data['appointment'])

    # Спрашиваем про проблему
    msg = bot.send_message(message.chat.id, "Опишите проблему, с которой вы обращаетесь:")
    bot.register_next_step_handler(msg, set_problem)


def set_problem(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    # Сохраняем описание проблемы
    user_data['appointment']['problem'] = message.text
    print(user_id, 'problem', user_data['appointment'])

    # Спрашиваем про запчасти с inline-кнопками
    markup = types.InlineKeyboardMarkup()
    yes_btn = types.InlineKeyboardButton("Да", callback_data="set_parts:yes")
    no_btn = types.InlineKeyboardButton("Нет", callback_data="set_parts:no")
    markup.add(yes_btn, no_btn)

    bot.send_message(message.chat.id, "Нужно ли заранее заказать запчасти?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_parts:'))
def handle_set_parts(call):
    data = call.data.split(':')
    is_need = 1 if data[1] == 'yes' else 0
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    # Сохраняем информацию о запчастях
    user_data['appointment']['parts'] = is_need
    print(user_id, 'parts', user_data['appointment'])

    # НЕ спрашиваем детали, сразу переходим к подтверждению
    confirm(user_id)
    bot.answer_callback_query(call.id)


def confirm(user_id):
    user_data = get_user_data(user_id)
    appointment = user_data['appointment']
    print(user_id, 'confirm', user_data['appointment'])

    # Формируем сводку данных
    summary = "📋 Проверьте данные записи:\n\n"
    summary += f"📅 Дата: {user_data.get('date', 'не указана')}\n"
    summary += f"⏰ Время: {user_data.get('time', 'не указано')}\n"
    summary += f"🚗 VIN: {appointment.get('vin', 'не указан')}\n"
    summary += f"🔧 Проблема: {appointment.get('problem', 'не указана')}\n"
    summary += f"📦 Нужны запчасти: {'Да' if appointment.get('parts') == 1 else 'Нет'}\n"

    # Отправляем сводку и предлагаем подтвердить
    markup = types.InlineKeyboardMarkup()
    confirm_btn = types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")
    cancel_btn = types.InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
    markup.add(confirm_btn, cancel_btn)

    bot.send_message(user_data['chat_id'], summary, reply_markup=markup)



# какие данные менять
def which_type_to_change(message, type):
    return 0


if __name__ == '__main__':
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    print("Бот запущен!")
