from datetime import date, timedelta
import telebot
from django.urls import re_path
from telegram_bot_calendar import DetailedTelegramCalendar, WMonthTelegramCalendar
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
import config
from db import vin_info, Table, Appointment
from ляляля import MyTranslationCalendar
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# === CONFIGURATION ===

TOKEN = config.TOKEN_SECOND
GROUP_CHAT_ID = config.chat_id

bot = telebot.TeleBot(TOKEN)
# Хранилище сессий пользователей
user_sessions = {}


def get_user_data(user_id):
    """Получает или создает данные пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'current_app': 0,
            'chat_id': 0,
            'username': f"user_{user_id}",
            'notes_data': {},
            'editing_note_id': None,
            'editing_note_text': None,
            'appointment': {'problem': '', 'vin': '', 'parts': 0, 'time': '', 'date': '', 'problem_type': ''},

        }
    return user_sessions[user_id]


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
def delete(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    bot.send_message(user_data['chat_id'],
                     f"Введите <code>Подтвердить</code> чтобы удалить запись", parse_mode='HTML')
    bot.register_next_step_handler(call.message, confrim_delete)

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
def handle_appointment_calendar(call):
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
def duration(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    msg = bot.send_message(chat_id=user_data['chat_id'], text='введите длительность')
    bot.register_next_step_handler(msg, duration_handler)


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
def probl(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_data = get_user_data(user_id)
    msg = bot.send_message(chat_id=user_data['chat_id'], text='введите проблему')
    bot.register_next_step_handler(msg, probl_handler)


def probl_handler(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    at = Appointment(user_data['current_app'])
    at.set_problem(message.text)
    msg = bot.send_message(chat_id=user_data['chat_id'], text=f'проблема: {message.text}')
    # Вместо start_command(message) вызываем функцию показа меню опций
    show_options_menu(user_id, message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'mech')
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
def handle_time(call):
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
