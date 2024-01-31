import json


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
    def __init__(self, db: range):
        self.identity = db[0]
        self.name = db[1]
        self.description = db[2]
        self.deadline = db[3]

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

    def to_dict(self):
        return self.__dict__


class Commands:
    ADD_HW = "Добавить дз"
    ADD_INFO = "Добавить информацию к дз"
    COMPLETE_HW = "Отметить дз как выполнено"