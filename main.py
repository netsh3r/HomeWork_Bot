import telebot
import psycopg2
from telebot import types
import shelve
from Models import *
import datetime
import schedule
import threading

bot = telebot.TeleBot('')
connection = psycopg2.connect(user='postgres', password='123', host='127.0.0.1', port='5432', database='OPD')
cursor = connection.cursor()
root_token_id = 0


@bot.message_handler(commands=['start'])
def send_welcome(message):
    storage = shelve.open('shelve')
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
    show_commands(message)
    storage.close()


@bot.message_handler(commands=["root_start_planer"])
def start_planer(message):
    if message.chat.id == root_token_id:
        planer()


@bot.message_handler(commands=['root_clean'])
def clean_storage(message):
    if message.chat.id == root_token_id:
        storage = shelve.open('shelve', flag='n')
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
        try:
            sql = f"INSERT INTO homeworks (name, description, deadline) VALUES ('{storage[f"{message.chat.id}-hw_name"]}','{storage[f"{message.chat.id}-hw_description"]}',Date('{message.text}')) RETURNING id"
            cursor.execute(sql)
            hw_id = cursor.fetchone()[0]
            cursor.execute(f"INSERT INTO user_hw (hw_id, user_id) VALUES ('{hw_id}','{storage[f"{message.chat.id}-user_id"]}')")
            connection.commit()
            bot.send_message(message.chat.id, f"Домашнее задание {storage[f"{message.chat.id}-hw_name"]} успешно добавлено")
        except Exception:
            bot.send_message(message.chat.id, "Что то пошло не так")
            connection.rollback()
        finally:
            del storage[f"{message.chat.id}-last_command"]
            del storage[f"{message.chat.id}-hw_step"]
            del storage[f"{message.chat.id}-hw_name"]
            del storage[f"{message.chat.id}-hw_description"]
            show_commands(message)


def add_info(message):
    storage = shelve.open("shelve")
    show_hw(message, storage, InternalCommands.ADD_INFO)
    storage.close()


def add_internal_info(message, identity=None):
    storage = shelve.open('shelve')
    storage[f"{message.chat.id}-last_command"] = InternalCommands.ADD_INFO
    if identity is None:
        identity = storage[f"{message.chat.id}-selected_message"]
    else:
        storage[f"{message.chat.id}-selected_message"] = identity

    if storage.get(f"{message.chat.id}-{identity}-step", None) != "name":
        storage[f"{message.chat.id}-{identity}-step"] = "name"
        bot.send_message(message.chat.id, "Введите комментарий: ")
    else:
        cursor.execute(f"insert into {HomeworkAdditional.TABLE_NAME} (hw_id, info) values ({identity}, '{message.text}')")
        connection.commit()
        del storage[f"{message.chat.id}-{identity}-step"]
        show_commands(message)


def show_hw_additional(message, identity):
    markup = types.InlineKeyboardMarkup(row_width=1)
    cursor.execute(f"select id, hw_id, info from {HomeworkAdditional.TABLE_NAME} where hw_id={identity}")
    hw_info = [HomeworkAdditional(*hw_ad) for hw_ad in cursor.fetchall()]
    buttons = [types.InlineKeyboardButton(text=x.info, callback_data=f"{InternalCommands.REMOVE_INFO}-{identity}-{x.identity}") for x in hw_info]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Выберите информацию", reply_markup=markup)


def remove_info(message, identity_hw, identity_info=None):
    if identity_info is not None:
        cursor.execute(f"delete from {HomeworkAdditional.TABLE_NAME} where id={identity_info}")
        connection.commit()

    show_hw_additional(message, identity_hw)


def edit_hw(message, identity=None):
    storage = shelve.open('shelve')
    if identity is not None:
        storage.pop(f"{message.chat.id}-{[f"{message.chat.id}-selected_message"]}-hw_step", None)
        storage.pop(f"{message.chat.id}-{[f"{message.chat.id}-selected_message"]}-hw_name", None)
        storage.pop(f"{message.chat.id}-{[f"{message.chat.id}-selected_message"]}-hw_description", None)
        storage.pop(f"{message.chat.id}-{[f"{message.chat.id}-selected_message"]}-last_command", None)
        storage[f"{message.chat.id}-selected_message"] = identity
    else:
        identity = storage[f"{message.chat.id}-selected_message"]

    storage[f"{message.chat.id}-last_command"] = InternalCommands.EDIT_HW
    if not storage.keys().__contains__(f"{message.chat.id}-{identity}-hw_step"):
        storage[f"{message.chat.id}-{identity}-hw_step"] = "name"
        bot.send_message(message.chat.id, "Введите название предмета:")
    elif storage[f"{message.chat.id}-{identity}-hw_step"] == "name":
        storage[f"{message.chat.id}-{identity}-hw_name"] = message.text
        storage[f"{message.chat.id}-{identity}-hw_step"] = "description"
        bot.send_message(message.chat.id, "Введите описание предмета:")
    elif storage[f"{message.chat.id}-{identity}-hw_step"] == "description":
        storage[f"{message.chat.id}-{identity}-hw_description"] = message.text
        storage[f"{message.chat.id}-{identity}-hw_step"] = "deadline"
        bot.send_message(message.chat.id, "Введите дедлайн предмета в формате yyyy-MM-dd (пример: 1990-01-23):")
    elif storage[f"{message.chat.id}-{identity}-hw_step"] == "deadline":
        try:
            sql = f"update homeworks SET name = '{storage[f"{message.chat.id}-{identity}-hw_name"]}', description = '{storage[f"{message.chat.id}-{identity}-hw_description"]}', deadline = '{message.text}' where id = {identity}"
            cursor.execute(sql)
            connection.commit()
        except Exception:
            bot.send_message(message.chat.id, "Что то пошло не так")
            connection.rollback()
        finally:
            del storage[f"{message.chat.id}-{identity}-hw_step"]
            del storage[f"{message.chat.id}-{identity}-hw_name"]
            del storage[f"{message.chat.id}-{identity}-hw_description"]
            del storage[f"{message.chat.id}-last_command"]
            show_commands(message)


def cls_to_dict(obj):
    if isinstance(obj, datetime.date):
        return dict(year=obj.year, month=obj.month, day=obj.day)
    return obj.__dict__


def show_hw(message, storage=None, callback_data=InternalCommands.SHOW_HW_INFO):
    if storage is None:
        storage = shelve.open('shelve')
    chat_id = message.chat.id if isinstance(message, types.Message) else message
    cursor.execute(
        f"select * from homeworks hw inner join user_hw uhw on uhw.user_id = '{storage[f"{chat_id}-user_id"]}' where hw.completed = false and hw.id = uhw.hw_id")
    hws = [Homework(x) for x in cursor.fetchall()]
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [types.InlineKeyboardButton(text=x.name, callback_data=f"{callback_data}-{x.identity}") for x in hws]
    markup.add(*buttons)
    bot.send_message(chat_id, 'текущие домашние задания (Нажмите чтобы посмотреть дополнительную информацию)', reply_markup=markup)


def show_hw_info(message, identity):
    cursor.execute(f"select * from {Homework.TABLE_NAME} where id = '{identity}' limit 1")
    hw = Homework(cursor.fetchone())
    cursor.execute(f"select * from {HomeworkAdditional.TABLE_NAME} where hw_id = '{hw.identity}'")
    hw_additionals = [HomeworkAdditional(*x) for x in cursor.fetchall()]
    markup = types.InlineKeyboardMarkup()
    row1 = [
        types.InlineKeyboardButton('Добавить комментарий', callback_data=f"{InternalCommands.ADD_INFO}-{identity}"),
        types.InlineKeyboardButton('Удалить комментарий', callback_data=f"{InternalCommands.REMOVE_INFO}-{identity}")
    ]
    row2 = [
        types.InlineKeyboardButton('Редактировать запись', callback_data=f"{InternalCommands.EDIT_HW}-{identity}"),
        types.InlineKeyboardButton('Отметить как выполнено', callback_data=f"{Commands.COMPLETE_HW}-{identity}")
    ]
    markup.row(*row1)
    markup.row(*row2)
    bot.send_message(message.chat.id, f"{hw.to_str()}\r\n\r\n*Комментарии*\r\n{"\r\n".join([f" - {x.info}" for x in hw_additionals])}", reply_markup=markup, parse_mode= 'Markdown')


@bot.message_handler(commands=['complete'])
def complete_hw(message, identity=None):
    storage = shelve.open('shelve')
    if identity:
        cursor.execute(f"update homeworks set completed = true where id = {identity}")
        connection.commit()
    show_hw(message, storage)
    storage.close()


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    data = call.data.split("-")
    cmd = data[0]
    command_dict[cmd](call.message, *data[1::])


command_dict = {
    Commands.ADD_HW: create_hw,
    Commands.ADD_INFO: add_info,
    Commands.COMPLETE_HW: complete_hw,
    Commands.SHOW_HWS: show_hw,
    InternalCommands.SHOW_HW_INFO: show_hw_info,
    InternalCommands.ADD_INFO: add_internal_info,
    InternalCommands.REMOVE_INFO: remove_info,
    InternalCommands.EDIT_HW: edit_hw
}


def show_commands(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [types.KeyboardButton(text=str(Commands.__dict__[x])) for x in Helper.get_constants(Commands)]
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
        send_welcome(message)
    storage.close()


def send_message():
    storage = shelve.open('shelve')
    cursor.execute("select * from users")
    users = [User(x) for x in cursor.fetchall()]
    for user in users:
        show_hw(user.token_id, storage)
    storage.close()


def planer():
    schedule.run_pending()
    reminder_timer = threading.Timer(1, planer)
    reminder_timer.start()


schedule.every().day.at("09:00").do(send_message)
schedule.every().day.at("21:00").do(send_message)


bot.polling(none_stop=True)
