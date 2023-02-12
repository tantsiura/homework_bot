class ParseStatusError(Exception):
    def __init__(self, text):
        message = (
            f'Парсинг ответа API: {text}'
        )
        super().__init__(message)
