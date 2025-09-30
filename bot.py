from datetime import date, timedelta
import telebot
from telegram_bot_calendar import DetailedTelegramCalendar, WMonthTelegramCalendar
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
import config
from db import vin_info, Table
from ляляля import MyTranslationCalendar
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# === CONFIGURATION ===

TOKEN = config.TOKEN
GROUP_CHAT_ID = config.chat_id

bot = telebot.TeleBot(TOKEN)
# Хранилище сессий пользователей
user_sessions = {}
print("MyTranslationCalendar methods:", dir(MyTranslationCalendar))
print("WMonthTelegramCalendar methods:", dir(WMonthTelegramCalendar))

# Или проверим callback данные

#
# @bot.callback_query_handler(func=lambda call: True)
# def debug_callback(call):
#     print(f"Full callback data: {call.data}")



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
            'appointment': {'problem': '', 'vin': '', 'parts': 0, 'time': '', 'date': '', 'problem_type': ''},
            'is_editing': False,  # Флаг для отслеживания режима редактирования
            'is_asked': False,
            'is_skip': False
        }
    return user_sessions[user_id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('command:'))
def handle_command_callback(call):
    user_id = call.from_user.id
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

    # if command == '/set_time':
    #     set_time(mock_message)
    if command == '/set_problem':
        set_problem(mock_message)
    elif command == '/set_vin':
        set_vin(mock_message)
    elif command == '/sign_up':
        sign_up(mock_message)
    elif command == '/change_appointment':
        change_appointment(mock_message)
    elif command == '/change_time':
        change_time(mock_message)
    elif command == '/change_vin':
        change_vin(mock_message)
    elif command == '/change_problem':
        change_problem(mock_message)
    elif command == '/change_parts':
        change_parts(mock_message)
    elif command == '/cancel_changes':
        cancel_changes(call)
    elif command == '/change_phone':
        change_phone(mock_message)

    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in handle_command_callback: {e}")

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    user_data['username'] = username
    user_data['chat_id'] = message.chat.id
    show_second_menu(user_data['chat_id'])


def show_second_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)

    btn_set_id = InlineKeyboardButton(
        text="Записаться",
        callback_data="command:/sign_up"
    )
    btn_change_appointment = InlineKeyboardButton(
        text="Изменить заявку",
        callback_data="command:/change_appointment"
    )

    markup.add(btn_set_id, btn_change_appointment)
    bot.send_message(
        chat_id,
        "<b>Главное меню</b>\n\n",
        parse_mode='HTML',
        reply_markup=markup
    )


def sign_up(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = False  # Сбрасываем флаг редактирования при новой записи
    user_data['is_asked'] = False  # Сбрасываем флаг редактирования при новой записи

    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = MyTranslationCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(user_data['chat_id'], f"<b>Заявку можно будет изменить в конце</b>\nВыберите предпочтительную дату, возможно, окончательная дата будет иной \n<b><u>(сб, вс - нерабочие дни)</u></b>",
                     parse_mode='HTML', reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith('my_0'))
def handle_appointment_calendar(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in handle_appointment_calendar: {e}")
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)

    result, key, step = MyTranslationCalendar(min_date=min_date, max_date=max_date, locale='ru').process(call.data)

    if not result and key:
        bot.edit_message_text(f"Выберите дату", user_data['chat_id'], call.message.message_id, reply_markup=key)
    elif result:
        if result.weekday() >= 5:
            bot.send_message(user_data['chat_id'], 'Суббота и воскресенье - нерабочие дни, выберите другой день')
            return

        user_data['appointment']['date'] = str(result)
        bot.edit_message_text(f"Вы выбрали: {result}", user_data['chat_id'], call.message.message_id)

        db = Table()
        times = db.check_day(date=user_data['appointment']['date'])
        markup = InlineKeyboardMarkup(row_width=1)

        for time, status in times.items():
            if status:
                btn_time = InlineKeyboardButton(text=f"{time}:00", callback_data=f'time!{time}')
                markup.add(btn_time)

        if times:
            bot.send_message(call.message.chat.id, f"Выберите время", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, f"В этот день нет свободных дат, пожалуйста, выберите другую дату")
            sign_up(call.message)


# ВРЕМЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('time!'))
def handle_time(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in handle time: {e}")
    try:
        data = call.data.split('!')
        time_val = int(data[1])
        user_id = call.from_user.id
        user_data = get_user_data(user_id)

        user_data['appointment']['time'] = f"{time_val:02d}:00"

        # Редактируем сообщение с кнопками времени
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Вы выбрали: {time_val:02d}:00"
        )

        if user_data['is_editing']:
            confirm(user_id)
        else:
            msg = bot.send_message(call.message.chat.id, "Введите номер, марку и модель автомобиля")
            bot.register_next_step_handler(msg, set_model)

    except Exception as e:
        print(f"Error in handle_time: {e}")


def change_time(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования

    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = MyTranslationCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(user_data['chat_id'], f"Выберите новую дату", reply_markup=calendar)


# def set_time(message):
#     user_id = message.from_user.id
#     user_data = get_user_data(user_id)
#     time_text = message.text.strip()
#     user_data['appointment']['time'] = time_text
#     bot.send_message(message.chat.id, "Введите номер марку и модель автомобиля")
#     bot.register_next_step_handler(message, set_model)

# ВРЕМЯ

# МАРКА МОДЕЛЬ
def set_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['model'] = message.text
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="Пропустить",
                                    callback_data='skip_vin'))
    bot.send_message(message.chat.id, "Введите VIN\nЕсли не знаете или не уверены -нажмите пропустить",
                     reply_markup=markup)
    bot.register_next_step_handler(message, set_vin)

def change_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования

    bot.send_message(user_data['chat_id'], "Введите номер, марку и модель:")
    bot.register_next_step_handler(message, update_phone)


def update_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['model'] = message.text
    bot.send_message(user_data['chat_id'], "✅ Информация обновлена обновлена")
    confirm(user_id)
# МАРКА МОДЕЛЬ


# VIN
@bot.callback_query_handler(func=lambda call: call.data == 'skip_vin')
def skip_vin(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    try:
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        user_data['appointment']['vin'] = "не указан"
        # Убираем кнопки после нажатия
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        # Отправляем новое сообщение для описания проблемы
        if not user_data['is_asked']:
            user_data['is_asked'] = True
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text='Электрика', callback_data='type:electr'))
            markup.add(InlineKeyboardButton(text='Подвеска', callback_data='type:podv'))
            markup.add(InlineKeyboardButton(text='Двигатель', callback_data='type:dvig'))
            markup.add(InlineKeyboardButton(text='Шиномонтаж', callback_data='type:shinomontazh'))
            markup.add(InlineKeyboardButton(text='Не знаю', callback_data='type:idk'))
            msg = bot.send_message(
                call.message.chat.id,
                "Выберите тип проблемы, с которой вы обращаетесь",
                reply_markup=markup
            )
            bot.register_next_step_handler(msg, type_of_problem)

    except Exception as e:
        print(f"Error in skip_vin: {e}")


def set_vin(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        if not user_data['is_asked']:
            user_data['is_asked'] = True
            user_data['appointment']['vin'] = message.text
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text='Электрика', callback_data='type:electr'))
            markup.add(InlineKeyboardButton(text='Подвеска', callback_data='type:podv'))
            markup.add(InlineKeyboardButton(text='Двигатель', callback_data='type:dvig'))
            markup.add(InlineKeyboardButton(text='Шиномонтаж', callback_data='type:shinomontazh'))
            markup.add(InlineKeyboardButton(text='Не знаю', callback_data='type:idk'))

            # markup.add(InlineKeyboardButton(text='Не знаю', callback_data='type:nothing'))
            msg = bot.send_message(
                message.chat.id,
                "Выберите тип проблемы, с которой вы обращаетесь",
                reply_markup=markup #, или опишите ее"
            )

    except Exception as e:
        print(f"Error in set_vin: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('type:'))
def type_of_problem(call):
    try:
        # Пытаемся ответить на callback, но если он устарел - игнорируем ошибку
        bot.answer_callback_query(call.id)
    except Exception as e:
        # Просто логируем ошибку, но не прерываем выполнение
        logger.warning(f"Callback query expired: {e}")  # Исправлено
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    print(call.data, call.message, sep='\n')
    data = call.data.split(':')
    match data[1]:
        case 'electr':
            user_data['appointment']['problem_type'] = "Электрика"
        case 'podv':
            user_data['appointment']['problem_type'] = "Подвеска"
        case 'dvig':
            user_data['appointment']['problem_type'] = "Двигатель"
        case 'shinomontazh':
            user_data['appointment']['problem_type'] = "Шиномонтаж"
        case 'idk':
            user_data['appointment']['problem_type'] = "Не знаю"
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )

    msg = bot.send_message(call.message.chat.id, 'Опишите проблему')  # Исправлено: call.message.chat.id
    bot.register_next_step_handler(msg, set_problem)
    return 1


def change_vin(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True
    markup = InlineKeyboardMarkup(row_width=1)
    # markup.add(InlineKeyboardButton(text="Пропустить",
    #                                 callback_data=''))
    bot.send_message(user_data['chat_id'], "Введите новый VIN", reply_markup=markup)
    bot.register_next_step_handler(message, update_vin)


def update_vin(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    if message.text.strip().lower() == "пропустить":
        user_data['appointment']['vin'] = "не указан"
    else:
        user_data['appointment']['vin'] = message.text

    bot.send_message(user_data['chat_id'], "✅ VIN обновлен")
    confirm(user_id)
# VIN

# ПРОБЛЕМА
def set_problem(message):

    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    user_data['appointment']['problem'] = message.text

    markup = InlineKeyboardMarkup()
    yes_btn = InlineKeyboardButton("Да", callback_data="set_parts:yes")
    no_btn = InlineKeyboardButton("Нет", callback_data="set_parts:no")
    idk = InlineKeyboardButton("Не знаю", callback_data="set_parts:idk")
    markup.add(yes_btn, no_btn, idk)
    bot.send_message(message.chat.id, "Нужно ли заранее заказать запчасти?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('upd_type:'))
def upd_type_of_problem(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    data = call.data.split(':')
    match data[1]:
        case 'electr':
            user_data['appointment']['problem_type'] = "Электрика"
        case 'podv':
            user_data['appointment']['problem_type'] = "Подвеска"
        case 'dvig':
            user_data['appointment']['problem_type'] = "Двигатель"
        case 'shinomontazh':
            user_data['appointment']['problem_type'] = "Двигатель"
        case 'nothing':
            user_data['appointment']['problem_type'] = "-"
    bot.send_message(user_data['chat_id'], text='Опишите проблему')
    bot.register_next_step_handler(call.message, update_problem)

def change_problem(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text='Электрика', callback_data='upd_type:electr'))
    markup.add(InlineKeyboardButton(text='Подвеска', callback_data='upd_type:podv'))
    markup.add(InlineKeyboardButton(text='Двигатель', callback_data='upd_type:dvig'))
    markup.add(InlineKeyboardButton(text='Шиномонтаж', callback_data='upd_type:shinomontazh'))
    bot.send_message(user_data['chat_id'], "Выберите тип проблемы:", reply_markup=markup)


def update_problem(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    user_data['appointment']['problem'] = message.text
    bot.send_message(user_data['chat_id'], "✅ Описание проблемы обновлено")
    confirm(user_id)


# ПРОБЛЕМА

# ЗАПЧАСТИ
@bot.callback_query_handler(func=lambda call: call.data.startswith('set_parts:'))
def handle_set_parts(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    data = call.data.split(':')
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    match data[1]:
        case 'yes':
            is_need = 'нужны'
        case 'no':
            is_need = 'не нужны'
        case 'idk':
            is_need = 'не уверен'
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    bot.send_message(user_data['chat_id'], "Введите номер телефона для связи")
    user_data['appointment']['parts'] = is_need
    bot.register_next_step_handler(call.message, set_phone)


def change_parts(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования

    markup = InlineKeyboardMarkup()
    yes_btn = InlineKeyboardButton("Да", callback_data="update_parts:yes")
    no_btn = InlineKeyboardButton("Нет", callback_data="update_parts:no")
    idk = InlineKeyboardButton("Не знаю", callback_data="update_parts:idk")
    markup.add(yes_btn, no_btn, idk)

    bot.send_message(user_data['chat_id'], "Нужно ли заранее заказать запчасти?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('update_parts:'))
def handle_update_parts(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    data = call.data.split(':')
    match data[1]:
        case 'yes':
            is_need = 'нужны'
        case 'no':
            is_need = 'не нужны'
        case 'idk':
            is_need = 'не уверен'
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    user_data['appointment']['parts'] = is_need
    bot.send_message(user_data['chat_id'], "✅ Информация о запчастях обновлена")
    # bot.answer_callback_query(call.id)
# ЗАПЧАСТИ

# НОМЕР
def set_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['phone'] = message.text
    confirm(user_id)

def change_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования

    bot.send_message(user_data['chat_id'], "Введите новый номер:")
    bot.register_next_step_handler(message, update_phone)


def update_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['phone'] = message.text
    bot.send_message(user_data['chat_id'], "✅ Номер обновлен")
    confirm(user_id)
# НОМЕР

# ЗАЯВКА
def change_appointment(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True
    if not user_data['appointment'] or not user_data['appointment'].get('date'):
        bot.send_message(user_data['chat_id'], "❌ У вас нет активной заявки для изменения.")
        return

    markup = InlineKeyboardMarkup(row_width=1)

    btn_change_time = InlineKeyboardButton(
        text="Изменить дату и время",
        callback_data="command:/change_time"
    )
    btn_change_vin = InlineKeyboardButton(
        text="Изменить VIN",
        callback_data="command:/change_vin"
    )
    btn_change_problem = InlineKeyboardButton(
        text="Изменить проблему",
        callback_data="command:/change_problem"
    )
    btn_change_parts = InlineKeyboardButton(
        text="Изменить заказ запчастей",
        callback_data="command:/change_parts"
    )
    btn_change_phone = InlineKeyboardButton(
        text="Изменить номер",
        callback_data="command:/change_phone"
    )

    markup.add(btn_change_time, btn_change_vin, btn_change_problem, btn_change_parts, btn_change_phone)

    appointment = user_data['appointment']
    current_info = (
        f"📋 <b>Текущие данные заявки:</b>\n\n"
        f"📅 Дата: {appointment.get('date', 'не указана')}\n"
        f"⏰ Время: {appointment.get('time', 'не указано')}\n"
        f"🚗 VIN: {appointment.get('vin', 'не указан')}\n"
        f"🔧 Проблема: {appointment.get('problem', 'не указана')}\n"
        f"📦 Нужны запчасти: {appointment.get('parts', 'не указано')}\n\n"
        f"Выберите, что хотите изменить:"
    )

    bot.send_message(
        user_data['chat_id'],
        current_info,
        parse_mode='HTML',
        reply_markup=markup
    )


def cancel_changes(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    bot.send_message(user_data['chat_id'], "❌ Изменения отменены")
    show_second_menu(user_data['chat_id'])


def confirm(user_id):
    user_data = get_user_data(user_id)
    appointment = user_data['appointment']

    summary = "📋 Проверьте данные записи:\n\n"
    summary += f"📅 Дата: {appointment.get('date', 'не указана')}\n"
    summary += f"⏰ Время: {appointment.get('time', 'не указано')}\n"
    summary += f"🚗 VIN: {appointment.get('vin', 'не указан')}\n"
    summary += f"🔧 Проблема: {appointment.get('problem_type', 'не указана')} | {appointment.get('problem', 'не указана')}\n"
    summary += f"📦 Нужны запчасти: {appointment.get('parts', 'не указано')}\n"
    summary += f"    Номер: {user_data['appointment']['phone']}"


    markup = InlineKeyboardMarkup(row_width=2)
    confirm_btn = InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")
    change_btn = InlineKeyboardButton("✏️ Изменить заявку", callback_data="command:/change_appointment")
    cancel_btn = InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
    markup.add(confirm_btn, change_btn, cancel_btn)

    bot.send_message(user_data['chat_id'], summary, reply_markup=markup)


# ЗАЯВКА

# ПОДТВЕРЖДЕНИЕ
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_yes'))
def handle_confirmation(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    if not user_data:
        bot.answer_callback_query(call.id, "Ошибка: данные не найдены!")
        return

    summary = (
        f"📅 Дата: {user_data['appointment']['date']}\n"
        f"🕒 Время: {user_data['appointment']['time']}\n"
        f"🕒 Время: {user_data['appointment']['model']}\n"
        f"🔢 VIN: {user_data['appointment']['vin']}\n"
        f"⚙️ Подобрать запчасти: {user_data['appointment']['parts']}\n"
        f"🛠️ Проблема:{user_data['appointment']['problem_type']} | {user_data['appointment']['problem']}\n"
        f"    Номер: {user_data['appointment']['phone']}"

    )

    bot.send_message(user_data['chat_id'], "✅ Ваша заявка отправлена")
    send_to_other_chat(call.from_user, GROUP_CHAT_ID, summary, user_data['appointment']['vin'])
    bot.answer_callback_query(call.id, "Заявка отправлена!")


def send_to_other_chat(user, target_chat_id, summary, vin):
    vin_inf = ''
    if vin != 'не указан':
        vin_inf = vin_info(vin)
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f'accepted:{user.id}'),
        InlineKeyboardButton("❌ Отклонить", callback_data=f'declined:{user.id}'),
        InlineKeyboardButton("записи на эту дату", callback_data=f'zapisi')
    )
    msg = (
        f"Username: @{user.username or 'нет'}\n"
        f"ID: {user.id}\n\n"
        f"\n{summary}\n"
        f"Информация по VIN:\n {', '.join(vin_inf) if vin_inf else 'Не указан'}"
    )
    bot.send_message(target_chat_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith(('accepted:', 'declined:')))
def handle_decision(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    data = call.data.split(':')
    action, target_user_id = data[0], data[1]
    moderator = call.from_user

    accepted = action == 'accepted'
    decision_text = "✅ Заявка принята" if accepted else "❌ Заявка отклонена"
    bot.send_message(int(target_user_id), f"{decision_text}. Если потребуется, с вами свяжутся.")

    edited_text = (
        f"{call.message.text}\n\n"
        f"{decision_text}: "
        f"{moderator.first_name} {moderator.last_name or ''} (@{moderator.username or 'нет'})"
    )

    if accepted:
        user_data = get_user_data(int(target_user_id))
        db = Table()
        db.add([
            user_data['appointment']['date'],
            user_data['appointment']['time'][:2],
            target_user_id,
            user_data['appointment']['problem_type']+'|'+user_data['appointment']['problem'],
            user_data['appointment']['vin'],
            user_data['appointment']['parts'],
            1,
            user_data['appointment']['model']

        ])

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=edited_text
    )


# ПОДТВЕРЖДЕНИЕ


@bot.callback_query_handler(func=lambda call: call.data.startswith('zapisi'))
def zapisi(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(GROUP_CHAT_ID, f"Выберите дату",
                     parse_mode='HTML', reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cbcal_0'))
def handle_view_calendar(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    min_date = date.today()
    max_date = min_date + timedelta(days=14)

    result, key, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').process(call.data)

    if not result and key:
        bot.edit_message_text(f"Выберите дату для просмотра записей",
                              call.message.chat.id, call.message.message_id, reply_markup=key)
    elif result:
        db = Table()
        appointments = db.appointments_by_date(str(result))
        mechs = {'1': 'Саша',
                 '2': 'Денис'}
        if not appointments:
            text = 'На эту дату нет записей'
        else:
            text = f"📅 Записи на {result}:\n\n"
            for time, problem, mechanic in appointments:
                text += f"🕒 {time}:00 - {problem}"
                if mechanic:
                    text += f", механик: {mechs[mechanic]}"
                text += "\n"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)


if __name__ == '__main__':
    print("Бот запущен!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
