import telebot
import psycopg2
from telebot import types
import shelve
from Models import *
import datetime
import schedule
import threading

bot = telebot.TeleBot('token')
connection = psycopg2.connect(user='postgres', password='123', host='127.0.0.1', port='5432', database='OPD')
cursor = connection.cursor()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    storage = shelve.open('shelve', flag='n')
    cursor.execute(f"SELECT * FROM users where token_id = '{message.chat.id}'")
    res = cursor.fetchone()
    user = User(res) if res is not None else None
    if not user:
        sql = f"insert into users (token_id, name) values ({message.chat.id}, '{message.from_user.username}') RETURNING *"
        cursor.execute(sql)
        user = User(cursor.fetchone())
        connection.commit()
    bot.send_message(message.chat.id, f"Здравствуйте {message.from_user.first_name}!")
    storage[f"{message.chat.id}-user_id"] = user.identity
    show_hw(storage, message.chat.id)
    show_commands(message)
    planer()
    storage.close()


def set_last_command(storage, chat_id, cmd):
    storage[f"{chat_id}-last_command"] = cmd


@bot.message_handler(commands=['create'])
def create_hw(message):
    storage = shelve.open('shelve')
    storage[f"{message.chat.id}-last_command"] = Commands.ADD_HW
    if not storage.keys().__contains__(f"{message.chat.id}-hw_step"):
        storage[f"{message.chat.id}-hw_step"] = "name"
        bot.send_message(message.chat.id, "Введите название предмета:")
    elif storage[f"{message.chat.id}-hw_step"] == "name":
        storage[f"{message.chat.id}-hw_name"] = message.text
        storage[f"{message.chat.id}-hw_step"] = "description"
        bot.send_message(message.chat.id, "Введите описание предмета:")
    elif storage[f"{message.chat.id}-hw_step"] == "description":
        storage[f"{message.chat.id}-hw_description"] = message.text
        storage[f"{message.chat.id}-hw_step"] = "deadline"
        bot.send_message(message.chat.id, "Введите дедлайн предмета в формате yyyy-MM-dd (пример: 1990-01-23):")
    elif storage[f"{message.chat.id}-hw_step"] == "deadline":
        sql = f"INSERT INTO homeworks (name, description, deadline) VALUES ('{storage[f"{message.chat.id}-hw_name"]}','{storage[f"{message.chat.id}-hw_description"]}',Date('{message.text}')) RETURNING id"
        cursor.execute(sql)
        hw_id = cursor.fetchone()[0]
        cursor.execute(f"INSERT INTO user_hw (hw_id, user_id) VALUES ('{hw_id}','{storage[f"{message.chat.id}-user_id"]}')")
        connection.commit()
        bot.send_message(message.chat.id, f"Домашнее задание {storage[f"{message.chat.id}-hw_name"]} успешно добавлено")
        del storage[f"{message.chat.id}-hw_step"]
        del storage[f"{message.chat.id}-hw_name"]
        del storage[f"{message.chat.id}-hw_description"]
        del storage[f"{message.chat.id}-last_command"]
    show_commands(message)


@bot.message_handler(commands=['add'])
def add_info(message):
    print("added")


def cls_to_dict(obj):
    if isinstance(obj, datetime.date):
        return dict(year=obj.year, month=obj.month, day=obj.day)
    return obj.__dict__


def show_hw(storage, chat_id):
    cursor.execute(
        f"select * from homeworks hw inner join user_hw uhw on uhw.user_id = '{storage[f"{chat_id}-user_id"]}' where hw.completed = false and hw.id = uhw.hw_id")
    hws = [Homework(x) for x in cursor.fetchall()]
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [types.InlineKeyboardButton(text=f"{x.identity}-{x.name}", callback_data=f"{Commands.COMPLETE_HW}-{x.identity}") for x in hws]
    markup.add(*buttons)
    bot.send_message(chat_id, 'текущие домашние задания (Нажмите на задание чтобы отметить как выполненное)', reply_markup=markup)


@bot.message_handler(commands=['complete'])
def complete_hw(message, identity=None):
    storage = shelve.open('shelve')
    if identity:
        cursor.execute(f"update homeworks set completed = true where id = {identity}")
        connection.commit()
    show_hw(storage, message.chat.id)
    storage.close()


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    data = call.data.split("-")
    cmd = data[0]
    command_dict[cmd](call.message, *data[1::])
    return True


command_dict = {
    Commands.ADD_HW: create_hw,
    Commands.ADD_INFO: add_info,
    Commands.COMPLETE_HW: complete_hw,
}


def show_commands(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [types.KeyboardButton(text=str(x)) for x in command_dict.keys()]
    markup.add(*buttons)
    bot.send_message(message.chat.id, text="Выберите команду", reply_markup=markup)


# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    storage = shelve.open('shelve')
    if command_dict.keys().__contains__(message.text):
        command_dict[message.text](message)
    elif storage.keys().__contains__(f"{message.chat.id}-last_command") and command_dict.keys().__contains__(storage[f"{message.chat.id}-last_command"]):
        command_dict[storage[f"{message.chat.id}-last_command"]](message)
    else:
        show_commands(message)
    storage.close()


def send_message():
    storage = shelve.open('shelve')
    cursor.execute("select * from users")
    users = [User(x) for x in cursor.fetchall()]
    for user in users:
        show_hw(storage, user.token_id)
    storage.close()


def planer():
    schedule.run_pending()
    reminder_timer = threading.Timer(1, planer)
    reminder_timer.start()


schedule.every().day.at("09:00").do(send_message)
schedule.every().day.at("21:00").do(send_message)


bot.polling(none_stop=True)
