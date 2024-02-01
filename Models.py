import json
import inspect


class HomeworkAdditional:
    TABLE_NAME = "hw_addition"
    def __init__(self, identity, hw_id, info):
        self.identity = identity
        self.hw_id = hw_id
        self.info = info


class CompleteData:
    def __init__(self, identity):
        self.identity = identity

    def get_callback(self):
        return CallbackData(Commands.COMPLETE_HW, self.identity)


class CallbackData:
    def __init__(self, cmd, obj):
        self.cmd = cmd
        self.obj = obj


class User:
    def __init__(self, db: range):
        self.identity = db[0]
        self.name = db[1]
        self.token_id = db[2]


class Homework:
    TABLE_NAME = "homeworks"

    def __init__(self, db: range):
        self.identity = db[0]
        self.name = db[1]
        self.description = db[2]
        self.deadline = db[3]

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

    def to_str(self):
        return f"Название предмета: {self.name}\r\nОписание предмета: {self.description}\r\nСрок выполнения: {self.deadline}"

    def to_dict(self):
        return self.__dict__


class Commands:
    ADD_HW = "Добавить дз"
    ADD_INFO = "Добавить комментарий к дз"
    COMPLETE_HW = "Отметить дз как выполнено"
    SHOW_HWS = "Отобразить список ДЗ"


class Helper:
    @staticmethod
    def _is_props(v):
        return isinstance(v, property)

    @staticmethod
    def get_props(c):
        return [name for name, value in inspect.getmembers(c, Helper._is_props)]

    @staticmethod
    def get_constants(c):
        return [name for name in vars(c) if not name.startswith("_")]


class InternalCommands:
    SHOW_HW_INFO = "SHOW_HW_INFO"
    ADD_INFO = "ADD_INFO"
    REMOVE_INFO = "REMOVE_INFO"
    EDIT_HW = "EDIT_HW"