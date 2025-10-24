from datetime import date, timedelta
import telebot
from telegram_bot_calendar import DetailedTelegramCalendar, WMonthTelegramCalendar
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
import config
from db import vin_info, Table, Appointment
from yghbujn import duration
from ляляля import MyTranslationCalendar
import telebot
import traceback
import logging
from typing import Optional
from back import *
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# === CONFIGURATION ===

TOKEN = config.TOKEN
GROUP_CHAT_ID = config.test_chat_id

bot = telebot.TeleBot(config.TEST_TOKEN)
# Хранилище сессий пользователей
user_sessions = {}
ADMIN_ID = 997097309


# Или проверим callback данные

#
# @bot.callback_query_handler(func=lambda call: True)
# def debug_callback(call):
#     print(f"Full callback data: {call.data}")

def send_error_to_admin(error_message: str, user_info):
    """Отправляет сообщение об ошибке администратору"""
    try:
        message = f"🚨 Ошибка в боте\n\n"
        message += f"Ошибка: {error_message}\n\n"

        if user_info:
            message += f"Пользователь: {user_info}\n"

        bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


def error_handler(func):
    """Декоратор для обработки ошибок"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Получаем информацию об ошибке
            error_traceback = traceback.format_exc()
            error_message = f"{type(e).__name__}: {str(e)}"

            # Получаем информацию о пользователе, если есть
            user_info = None
            if args and hasattr(args[0], 'from_user'):
                user = args[0].from_user
                user_info = f"@{user.username} ({user.first_name} {user.last_name or ''}) ID: {user.id}"

            # Логируем ошибку
            logger.error(f"Ошибка в функции {func.__name__}: {error_message}")
            logger.error(f"Traceback: {error_traceback}")

            # Отправляем администратору
            full_error_info = f"{error_message}\n\n```\n{error_traceback}\n```"
            send_error_to_admin(full_error_info, user_info)
            #
            # # Отправляем пользователю сообщение об ошибке
            # if args and hasattr(args[0], 'chat'):
            #     try:
            #         bot.send_message(
            #             args[0].chat.id,
            #             "❌ Произошла ошибка. Администратор уже уведомлен."
            #         )
            #     except:
            #         pass

    return wrapper


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
@error_handler
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
    # elif command == '/set_vin':
    #     set_vin(mock_message)
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
@error_handler
def start_command(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    user_data['username'] = username
    user_data['chat_id'] = message.chat.id
    show_second_menu(user_data['chat_id'])


@error_handler
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


@error_handler
def sign_up(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = False  # Сбрасываем флаг редактирования при новой записи
    user_data['is_asked'] = False  # Сбрасываем флаг редактирования при новой записи

    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = MyTranslationCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(user_data['chat_id'],
                     f"<b>Заявку можно будет изменить в конце</b>\nВыберите предпочтительную дату, возможно, окончательная дата будет иной \n<b><u>(сб, вс - нерабочие дни)</u></b>",
                     parse_mode='HTML', reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith('my_0'))
@error_handler
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
        result = str(result)
        bot.edit_message_text(f"1/7\nДата: {result[-2] + result[-1] + '.' + result[5] + result[6] + '.' + result[:4]}",
                              user_data['chat_id'], call.message.message_id)

        db = Table()
        times = db.get_workload_by_date(target_date=user_data['appointment']['date'])
        markup = InlineKeyboardMarkup(row_width=1)
        for time, status in times.items():
            if status == 0:
                btn_time = InlineKeyboardButton(text=f"{time}:00 🟩", callback_data=f'time!{time}')
                markup.add(btn_time)
            if status == 1:
                btn_time = InlineKeyboardButton(text=f"{time}:00 🟨", callback_data=f'time!{time}')
                markup.add(btn_time)
            if status == 2:
                btn_time = InlineKeyboardButton(text=f"{time}:00 🟧", callback_data=f'time!{time}')
                markup.add(btn_time)
            if status == 3:
                btn_time = InlineKeyboardButton(text=f"{time}:00 🟥", callback_data=f'time!{time}')
                markup.add(btn_time)

        if times:
            bot.send_message(call.message.chat.id,
                             f"Выберите предпочтительное время, возможно, окончательное время измениться\n🟩-низкая загруженность🟨-средняя🟧-высокая🟥-полная",
                             reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, f"В этот день нет свободных дат, пожалуйста, выберите другую дату")
            sign_up(call.message)


# ВРЕМЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('time!'))
@error_handler
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
            text=f"2/7\nВремя: {time_val:02d}:00"
        )

        if user_data['is_editing']:
            confirm(user_id)
        else:
            msg = bot.send_message(call.message.chat.id, "Введите номер, марку и модель автомобиля")
            bot.register_next_step_handler(msg, set_model)

    except Exception as e:
        print(f"Error in handle_time: {e}")


@error_handler
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
@error_handler
def set_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['model'] = message.text
    bot.send_message(
        user_data['chat_id'],
        f"3/7\nМодель: {user_data['appointment']['model']}"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="Пропустить",
                                    callback_data='skip_vin'))
    bot.send_message(message.chat.id, "Введите VIN\nЕсли не знаете или не уверены -нажмите пропустить",
                     reply_markup=markup)
    bot.register_next_step_handler(message, set_vin)


@error_handler
def change_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактированиe
    bot.send_message(user_data['chat_id'], "Введите номер, марку и модель:")
    bot.register_next_step_handler(message, update_phone)


@error_handler
def update_model(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['model'] = message.text

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"Модель обновлена: {user_data['appointment']['model']}"
    )

    confirm(user_id)


# МАРКА МОДЕЛЬ


# VIN
@bot.callback_query_handler(func=lambda call: call.data == 'skip_vin')
@error_handler
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

        # Отправляем новое сообщение вместо редактирования старого
        bot.send_message(
            user_data['chat_id'],
            f"4/7\nVIN: {user_data['appointment']['vin']}"
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

            bot.send_message(
                call.message.chat.id,
                "Выберите тип проблемы, с которой вы обращаетесь",
                reply_markup=markup
            )
            # Убираем register_next_step_handler так как используем callback'и

    except Exception as e:
        logger.error(f"Error in skip_vin: {e}")


@error_handler
def set_vin(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        if not user_data['is_asked']:
            user_data['is_asked'] = True
            user_data['appointment']['vin'] = message.text

            # Отправляем новое сообщение вместо редактирования
            bot.send_message(
                user_data['chat_id'],
                f"4/7\nVIN: {user_data['appointment']['vin']}"
            )

            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text='Электрика', callback_data='type:electr'))
            markup.add(InlineKeyboardButton(text='Подвеска', callback_data='type:podv'))
            markup.add(InlineKeyboardButton(text='Двигатель', callback_data='type:dvig'))
            markup.add(InlineKeyboardButton(text='Шиномонтаж', callback_data='type:shinomontazh'))
            markup.add(InlineKeyboardButton(text='Не знаю', callback_data='type:idk'))

            bot.send_message(
                message.chat.id,
                "Выберите тип проблемы, с которой вы обращаетесь",
                reply_markup=markup
            )

    except Exception as e:
        logger.error(f"Error in set_vin: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('type:'))
@error_handler
def type_of_problem(call):
    try:
        # Пытаемся ответить на callback, но если он устарел - игнорируем ошибку
        bot.answer_callback_query(call.id)
    except Exception as e:
        # Просто логируем ошибку, но не прерываем выполнение
        logger.warning(f"Callback query expired: {e}")  # Исправлено
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    try:
        data = call.data.split(':')
    except Exception as ex:
        print(ex)
    finally:
        print(call.data.split(':'))
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
            user_data['appointment']['problem_type'] = "Не знаю/Другое"
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )

    msg = bot.send_message(call.message.chat.id, 'Опишите проблему')  # Исправлено: call.message.chat.id
    bot.register_next_step_handler(msg, set_problem)
    return 1


@error_handler
def change_vin(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True
    markup = InlineKeyboardMarkup(row_width=1)
    # markup.add(InlineKeyboardButton(text="Пропустить",
    #                                 callback_data=''))
    bot.send_message(user_data['chat_id'], "Введите новый VIN", reply_markup=markup)
    bot.register_next_step_handler(message, update_vin)


@error_handler
def update_vin(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    if message.text.strip().lower() == "пропустить":
        user_data['appointment']['vin'] = "не указан"
    else:
        user_data['appointment']['vin'] = message.text

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"VIN обновлен: {user_data['appointment']['vin']}"
    )

    confirm(user_id)


# VIN

# ПРОБЛЕМА
@error_handler
def set_problem(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['problem'] = message.text

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"5/7\nПроблема: {user_data['appointment']['problem']}"
    )

    markup = InlineKeyboardMarkup()
    yes_btn = InlineKeyboardButton("Да", callback_data="set_parts:yes")
    no_btn = InlineKeyboardButton("Нет", callback_data="set_parts:no")
    idk = InlineKeyboardButton("Не знаю", callback_data="set_parts:idk")
    markup.add(yes_btn, no_btn, idk)
    bot.send_message(message.chat.id, "Нужно ли заранее заказать запчасти?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('upd_type:'))
@error_handler
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


@error_handler
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


@error_handler
def update_problem(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['problem'] = message.text
    bot.edit_message_text(f"Вы выбрали: {user_data['appointment']['problem']}", user_data['chat_id'],
                          message.message_id)
    bot.send_message(user_data['chat_id'], "✅ Описание проблемы обновлено")
    confirm(user_id)


# ПРОБЛЕМА

# ЗАПЧАСТИ
@bot.callback_query_handler(func=lambda call: call.data.startswith('set_parts:'))
@error_handler
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
    bot.edit_message_text(f"6/7\nЗапчасти: {user_data['appointment']['parts']}", user_data['chat_id'],
                          call.message.message_id)
    bot.register_next_step_handler(call.message, set_phone)


@error_handler
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
@error_handler
def handle_update_parts(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in handle_update_parts: {e}")

    data = call.data.split(':')
    parts_status = {
        'yes': 'нужны',
        'no': 'не нужны',
        'idk': 'не уверен'
    }

    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['parts'] = parts_status.get(data[1], 'не указано')

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"Запчасти: {user_data['appointment']['parts']}"
    )

    confirm(user_id)


# ЗАПЧАСТИ

# НОМЕР
@error_handler
def set_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['phone'] = message.text

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"7/7\nТелефон: {user_data['appointment']['phone']}"
    )

    confirm(user_id)


@error_handler
def change_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['is_editing'] = True  # Устанавливаем флаг редактирования

    bot.send_message(user_data['chat_id'], "Введите новый номер:")
    bot.register_next_step_handler(message, update_phone)


@error_handler
def update_phone(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data['appointment']['phone'] = message.text

    # Отправляем новое сообщение вместо редактирования
    bot.send_message(
        user_data['chat_id'],
        f"Телефон обновлен: {user_data['appointment']['phone']}"
    )

    confirm(user_id)


# НОМЕР

# ЗАЯВКА
@error_handler
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


@error_handler
def cancel_changes(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    bot.send_message(user_data['chat_id'], "❌ Изменения отменены")
    show_second_menu(user_data['chat_id'])


@error_handler
def confirm(user_id):
    user_data = get_user_data(user_id)
    # ap = Appointment(0)
    # info = ap.info_by_user(user_id=user_id)
    markup = InlineKeyboardMarkup()
    appointment = user_data['appointment']
    markup.add(InlineKeyboardButton(text='Удалить', callback_data='delete'), )
    # date, time, problem, mechanic, duration, lift, vin = info
    date = user_data['appointment']['date']
    text = 'Текущая запись:\n'
    text += f"📅Дата: {date[-2] + date[-1] + '.' + date[5] + date[6] + '.' + date[:4] if date != 'не указана' else 'не указана'}\n"
    text += f"⏰ Время: {appointment.get('time', 'не указано')}\n"
    text += f"🚗 VIN: {appointment.get('vin', 'не указан')}\n"
    text += f"🔧 Проблема: {appointment.get('problem', 'не указана')}\n"
    text += f"📦 Нужны запчасти: {appointment.get('parts', 'не указано')}\n\n"
    # text += f" Имя: {user_data['username']}\n"

    markup = InlineKeyboardMarkup(row_width=2)
    confirm_btn = InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")
    change_btn = InlineKeyboardButton("✏️ Изменить заявку", callback_data="command:/change_appointment")
    cancel_btn = InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
    markup.add(confirm_btn, change_btn, cancel_btn)

    bot.send_message(user_data['chat_id'], text, reply_markup=markup)


# ЗАЯВКА

# ПОДТВЕРЖДЕНИЕ
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_yes'))
@error_handler
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

    db = Table()
    db.add([
        user_data['appointment']['date'],
        user_data['appointment']['time'][:2],
        user_id,
        user_data['appointment']['problem_type'] + '|' + user_data['appointment']['problem'],
        user_data['appointment']['vin'],
        user_data['appointment']['parts'],
        1,
        user_data['appointment']['model'],
        user_data['appointment']['phone'],
        call.from_user.username
    ])
    # Редактируем существующее сообщение вместо отправки нового
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=call.message.text + "\n\n✅ Ваша заявка отправлена, ее рассмотрят как можно скорее",
        reply_markup=None  # Убираем все кнопки
    )

    user_data['last_message'] = call
    send_to_other_chat(call.from_user, GROUP_CHAT_ID, user_id)


@error_handler
def send_to_other_chat(user, target_chat_id, user_id):
    user_data = get_user_data(user_id)
    ap = Appointment(0)
    info = ap.info_by_user(user_id=user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Удалить', callback_data='delete'), )
    date, time, problem, mechanic, duration, lift, vin = info
    text = ''
    text += f"📅{date[-2] + date[-1] + '.' + date[5] + date[6] + '.' + date[:4]}\n"
    text += f"🕒{time}:00\n"
    text += f"🛠️ Проблема: {problem}\n"
    text += f"📞 Номер: {user_data['appointment']['phone']}\n"
    text += f" Имя: {user_data['username']}\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Удалить', callback_data='delete'), )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f'accepted:{user.id}'),
        InlineKeyboardButton("❌ Отклонить", callback_data=f'declined:{user.id}'),
        # InlineKeyboardButton("записи на эту дату", callback_data=f'zapisi')
    )
    msg = (
        f"Username: @{user.username or 'нет'}\n"
        f"ID: {user.id}\n\n"
        f"\n{text}\n"
        f"Информация по VIN:\n {', '.join(vin_info(vin)) if vin else 'Не указан'}"
    )
    bot.send_message(target_chat_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith(('accepted:', 'declined:')))
@error_handler
def handle_decision(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.warning(f"Callback expired in skip_vin: {e}")
    data = call.data.split(':')
    action, target_user_id = data[0], data[1]
    accepted = action == 'accepted'
    decision_text = "✅ Заявка принята" if accepted else "❌ Заявка отклонена"
    if accepted:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        ap = Appointment(0)
        info = ap.info_by_user(user_id=target_user_id)
        date = info[0]
        time = info[1]
        problem = info[2]
        bot.send_message(int(target_user_id),
                         f"{decision_text}\n📅Дата {date[-2] + date[-1] + '.' + date[5] + date[6] + '.' + date[:4]}\n🕒Время {time}:00\n🛠️Проблема {problem}\n Если потребуется, с вами свяжутся.")
    else:
        bot.send_message(int(target_user_id), f"{decision_text}")


# ПОДТВЕРЖДЕНИЕ

# НЕ УБИРАТЬ НЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬНЕ УБИРАТЬ
# @bot.callback_query_handler(func=lambda call: call.data.startswith('zapisi'))
# @error_handler
# def zapisi(call):
#     user_id = call.from_user.id
#     user_data = get_user_data(user_id)
#     min_date = date.today()
#     max_date = min_date + timedelta(days=14)
#     calendar, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
#     bot.send_message(GROUP_CHAT_ID, f"Выберите дату",
#                      parse_mode='HTML', reply_markup=calendar)

# @error_handler
# def send_to_mech(user_id):
#     user_data = get_user_data(user_id)
#     ap = Appointment(0)
#     info = ap.info_by_user(user_id=user_id)
#     markup = InlineKeyboardMarkup()
#     markup.add(InlineKeyboardButton(text='Удалить', callback_data='delete'), )
#     date, time, problem, mechanic, duration, lift, vin = info
#     text = ''
#     text += f"📅{date[-2] + date[-1] + '.' + date[5] + date[6] + '.' + date[:4]}\n"
#     text += f"🕒{time}:00\n"
#     text += f"🛠️ Проблема: {problem}\n"
#     text += f"📞 Номер: {user_data['appointment']['phone']}\n"
#     text += f" Имя: {user_data['username']}\n"
#
#     msg = (
#         f"Новая запись"
#         f"Username: @{user.username or 'нет'}\n"
#         f"ID: {user.id}\n\n"
#         f"\n{text}\n"
#         f"Информация по VIN:\n {', '.join(vin_info(vin)) if vin else 'Не указан'}"
#     )
#     mechs_id_list = [
# #                 1576118658, #саша солома
# #                 7645088510, #руслан
# #                 1497728313, #alexnader
# #                 1062205174] #денис
#     [bot.send_message(i, msg) for i in mechs_id_list]

@bot.callback_query_handler(func=lambda call: call.data.startswith('cbcal_0'))
@error_handler
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

# bot = telebot.TeleBot(TOKEN)
# Хранилище сессий пользователей

user_id_list = [5506674973, #макан
                997097309, #макар
                24260386,] #папа
#                 1576118658, #саша солома
#                 7645088510, #руслан
#                 1497728313, #alexnader
#                 1062205174] #денис
def id_handler(func):
    """Декоратор для обработки ошибок"""
    def wrapper(*args, **kwargs):
        user_info = None
        if args[0] in user_id_list:
            # print('first if')
            return func(*args, **kwargs)
        if args and hasattr(args[0], 'from_user'):
            user = args[0].from_user
            # print('second if')
            if user.id in user_id_list:
                return func(*args, **kwargs)
    return wrapper

# @id_handler
# def get_user_data(user_id):
#     """Получает или создает данные пользователя"""
#     if user_id not in user_sessions:
#         user_sessions[user_id] = {
#             'current_app': 0,
#             'chat_id': 0,
#             'username': f"user_{user_id}",
#             'notes_data': {},
#             'editing_note_id': None,
#             'editing_note_text': None,
#             'appointment': {'problem': '', 'vin': '', 'parts': 0, 'time': '', 'date': '', 'problem_type': ''},
#
#         }
#     return user_sessions[user_id]


@bot.message_handler(commands=['1'])
@id_handler
def start_command_back(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
    user_data['username'] = username
    user_data['chat_id'] = message.chat.id
    show_back_menu(user_data['chat_id'])


@id_handler
def show_back_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)

    btn_set_id = InlineKeyboardButton(
        text="Записи на сегодня",
        callback_data="today_appointments"
    )
    btn_change_appointment = InlineKeyboardButton(
        text="Выбрать заявку",
        callback_data="choose_appointment"
    )

    btn_mechs_workload = InlineKeyboardButton(
        text="Загруженность механиков",
        callback_data="mechs_workload"
    )

    markup.add(btn_set_id, btn_change_appointment, btn_mechs_workload)
    bot.send_message(
        chat_id,
        "<b>Главное меню</b>\n\n",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'today_appointments')
@id_handler
def today_appointments(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    db = Table()
    res = db.today_appointments()
    if not res:
        text = 'На эту дату нет записей'
    else:
        mechs = {'1': 'Саша',
                 '2': 'Денис',}
        liftt = {'1': '4',
                 '2': '2',
                 '3': 'без'}
        text = f"Записи на сегодня:\n\n"
        for time, problem, mechanic, duration, lift in res:
            text += f"🕒 {time}:00 - {problem}"
            text += f", механик: {mechanic}\n"
            text += f"      подъемник: {lift}"
            text += f" длительность: {duration}"
            text += "\n\n"
    bot.send_message(chat_id=user_data['chat_id'],
                     text=text)

@bot.callback_query_handler(func=lambda call: call.data == 'mechs_workload')
@id_handler
def choose_date_for_mechs_workload(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(user_data['chat_id'],
                     f"Выберите дату",
                     parse_mode='HTML', reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cbcal_0'))
@id_handler
def handle_date_for_mechs_workload_calendar(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)

    result, key, step = WMonthTelegramCalendar(min_date=min_date, max_date=max_date, locale='ru').process(call.data)

    if not result and key:
        bot.edit_message_text(f"Выберите дату", user_data['chat_id'], call.message.message_id, reply_markup=key)
    elif result:
        bot.edit_message_text(f"Вы выбрали: {result}", user_data['chat_id'], call.message.message_id)
        db = Table()
        res = db.appointments_by_date(str(result))
        print(res)
        text = ''
        if not res:
            text = 'На эту дату нет записей'
        else:
            mechs = {'Саша': '',
                     'Денис': '',
                     'Саша другой': ''}
            for time, problem, mechanic, duration, lift in res:
                mechs[mechanic] += f'🕒 {time}:00 - {time + duration}:00 \nПроблема: {problem}\nподъемник: {lift}\n'
        for mech, txt in mechs.items():
            print(mech, txt)
            if txt:
                text += f'{mech}:\n{txt}\n'
        bot.send_message(chat_id=user_data['chat_id'],
                         text=text)

#
# def mechs_workload(call):
#     bot.answer_callback_query(call.id)
#     user_id = call.from_user.id
#     user_data = get_user_data(user_id)
#     db = Table()
#     res = db.appointments_by_date()
#     if not res:
#         text = 'На эту дату нет записей'
#     else:
#         mechs = {'1': 'Саша',
#                  '2': 'Денис'}
#         liftt = {'1': '4',
#                  '2': '2',
#                  '3': 'без'}
#         text = f"Записи на сегодня:\n\n"
#         for time, problem, mechanic, duration, lift in res:
#             text += f"🕒 {time}:00 - {problem}"
#             text += f", механик: {mechs[str(mechanic)]}\n"
#             text += f"      подъемник: {liftt[str(lift)]}"
#             text += f" длительность: {duration}"
#             text += "\n\n"
#     bot.send_message(chat_id=user_data['chat_id'],
#                      text=text)

@bot.callback_query_handler(func=lambda call: call.data == 'choose_appointment')
@id_handler
def choose_appointment(call):
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    db = Table()
    res = db.not_confirmed_appointments()
    print(res)
    markup = InlineKeyboardMarkup()
    if not res:
        text = 'Нет записей'
    else:
        for id, date, time, problem in res:
            text = f"{date} {time}:00 - {problem}" #date[-2] + date[-1] + '.' + date[5] + date[6]
            markup.add(InlineKeyboardButton(text=text, callback_data=f'app:{id}'))
    text = f"Выберите запись"
    bot.send_message(chat_id=user_data['chat_id'],
                     text=text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('app:'))
@id_handler
def handle_choose_app(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    data = call.data.split(':')
    user_data['current_app'] = data[1]
    at = Appointment(data[1])
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Удалить запись', callback_data='delete'),)
    date_, time_, problem_, mechanic_, duration_, lift_ = at.info()[0]
    text = 'Текущая запись:\n'
    text += f"{date_[-2] + date_[-1] + '.' + date_[5] + date_[6]}"
    text += f" {time_}:00\n{problem_}\n"
    text += f"механик: {mechanic_}\n"
    text += f"подъемник: {lift_}\n"
    text += f"длительность: {duration_}"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text, reply_markup=markup
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Дата и время', callback_data='date_time'),
               InlineKeyboardButton(text='Проблема', callback_data='probl'),
               InlineKeyboardButton(text='Механик', callback_data='mech'),
               InlineKeyboardButton(text='Подъемник', callback_data='lift'),
               InlineKeyboardButton(text='Длительность', callback_data='duration'), )
    bot.send_message(chat_id=user_data['chat_id'], text='Выберите опцию', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'delete')
@id_handler
def delete(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    bot.send_message(user_data['chat_id'],
                     f"Введите <code>Подтвердить</code> чтобы удалить запись", parse_mode='HTML')
    bot.register_next_step_handler(call.message, confrim_delete)

@id_handler
def confrim_delete(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    if message.text == 'Подтвердить':
        db = Appointment(user_data['current_app'])
        result = db.delete_app()
        bot.send_message(message.chat.id, result)
    else:
        bot.send_message(message.chat.id, f'Вы отменили удаление записи:{user_data["current_app"]}')

@bot.callback_query_handler(func=lambda call: call.data == 'date_time')
@id_handler
def date_time(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    min_date = date.today()
    max_date = min_date + timedelta(days=14)
    calendar, step = MyTranslationCalendar(min_date=min_date, max_date=max_date, locale='ru').build()
    bot.send_message(user_data['chat_id'],
                     f"Выберите дату",
                     parse_mode='HTML', reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith('my_0'))
@id_handler
def handle_appointment_calendar_back(call):
    bot.answer_callback_query(call.id)
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
        times = [10, 11, 12, 13, 14, 15, 16, 17, 18]
        markup = InlineKeyboardMarkup(row_width=1)

        for time in times:
            btn_time = InlineKeyboardButton(text=f"{time}:00", callback_data=f'time!{time}')
            markup.add(btn_time)

        if times:
            bot.send_message(call.message.chat.id, f"Выберите время", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, f"В этот день нет свободных дат, пожалуйста, выберите другую дату")


# ВРЕМЯ
@bot.callback_query_handler(func=lambda call: call.data == 'duration')
@id_handler
def duration(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    msg = bot.send_message(chat_id=user_data['chat_id'], text='введите длительность')
    bot.register_next_step_handler(msg, duration_handler)


@id_handler
def duration_handler(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    at = Appointment(user_data['current_app'])
    print(message.text)
    at.set_duration(message.text)
    msg = bot.send_message(chat_id=user_data['chat_id'], text=f'длительность ремонта: {message.text}')
    # Вместо start_command(message) вызываем функцию показа меню опций
    show_options_menu(user_id, message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'probl')
@id_handler
def probl(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    msg = bot.send_message(chat_id=user_data['chat_id'], text='введите проблему')
    bot.register_next_step_handler(msg, probl_handler)


@id_handler
def probl_handler(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    at = Appointment(user_data['current_app'])
    at.set_problem(message.text)
    msg = bot.send_message(chat_id=user_data['chat_id'], text=f'проблема: {message.text}')
    # Вместо start_command(message) вызываем функцию показа меню опций
    show_options_menu(user_id, message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'mech')
@id_handler
def mech(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Саша', callback_data='mech:Саша'),
               InlineKeyboardButton(text='Денис', callback_data='mech:Денис'),
               InlineKeyboardButton(text='Саша другой', callback_data='mech:Саша другой'), )
    msg = bot.send_message(chat_id=user_data['chat_id'], text='Выберите механика', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('mech:'))
@id_handler
def mech_handler(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    data = call.data.split(":")[1]
    at = Appointment(user_data['current_app'])
    at.set_mechanic(data)
    msg = bot.send_message(chat_id=user_data['chat_id'], text=f'Механик: {data}')
    # Вместо start_command(msg) вызываем функцию показа меню опций
    show_options_menu(user_id, call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'lift')
@id_handler
def lift(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='4', callback_data='lift:4'),
               InlineKeyboardButton(text='2', callback_data='lift:2'),
               InlineKeyboardButton(text='Без', callback_data='lift:без'), )
    msg = bot.send_message(chat_id=user_data['chat_id'], text='Выберите подъемник', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('lift:'))
@id_handler
def lift_handler(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    data = call.data.split(":")[1]
    at = Appointment(user_data['current_app'])
    at.set_lift(data)
    msg = bot.send_message(chat_id=user_data['chat_id'], text=f'Подъемник: {data}')
    # Вместо start_command(msg) вызываем функцию показа меню опций
    show_options_menu(user_id, call.message.chat.id)


# ВРЕМЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('time!'))
@id_handler
def handle_time_back(call):
    bot.answer_callback_query(call.id)
    data = call.data.split('!')
    time_val = int(data[1])
    user_id = call.from_user.id
    user_data = get_user_data(user_id)

    user_data['appointment']['time'] = time_val

    # Редактируем сообщение с кнопками времени
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Вы выбрали:{user_data['appointment']['date']} {time_val:02d}:00"
    )
    at = Appointment(user_data['current_app'])
    print(user_data['current_app'], user_data['appointment']['time'])
    print(at.change_date_time(time=user_data['appointment']['time'], date=user_data['appointment']['date']))

    # Показываем меню опций после изменения времени
    show_options_menu(user_id, call.message.chat.id)


# Добавляем функцию для показа меню опций (аналогично handle_choose_app)
@id_handler
def show_options_menu(user_id, chat_id):
    """Показывает меню опций для выбранной записи (аналогично handle_choose_app)"""
    user_data = get_user_data(user_id)

    # Получаем информацию о текущей записи
    at = Appointment(user_data['current_app'])
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Удалить', callback_data='delete'),)
    try:
        date_, time_, problem_, mechanic_, duration_, lift_ = at.info()[0]
        text = 'Текущая запись:\n'
        text += f"{date_[-2] + date_[-1] + '.' + date_[5] + date_[6]}"
        text += f" {time_}:00\n{problem_}\n"
        text += f"механик: {mechanic_}\n"
        text += f"подъемник: {lift_}\n"
        text += f"длительность: {duration_}"

        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error getting appointment info: {e}")
        bot.send_message(chat_id, "Информация о записи")

    # Показываем меню опций
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Дата и время', callback_data='date_time'),
               InlineKeyboardButton(text='Проблема', callback_data='probl'),
               InlineKeyboardButton(text='Механик', callback_data='mech'),
               InlineKeyboardButton(text='Подъемник', callback_data='lift'),
               InlineKeyboardButton(text='Длительность', callback_data='duration'), )
    bot.send_message(chat_id=chat_id, text='Выберите опцию', reply_markup=markup)


if __name__ == '__main__':
    print("Бот запущен!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
