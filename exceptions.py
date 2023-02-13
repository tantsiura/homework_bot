class ParseStatusError(Exception):
    """Исключение, возникающее при наличии проблем с парсингом ответа API."""
    def __init__(self, text):
        message = (
            f'Парсинг ответа API: {text}'
        )
        super().__init__(message)


class EndpointIsUnavailable(Exception):
    """Исключение, возникающее при наличии проблем с запросами к API адресу"""
    
    pass


class HttpStatusCodeError(Exception):
    """Исключение, возникающее при status code != 200."""
    
    pass


class JsonApiError(Exception):
    """Исключение, возникающее при наличии проблем с преобразованием API адреса в json"""
    
    pass


class EmptyResponseError(Exception):
    """Исключение, возникающее при отсутствии данных в ответе API"""
    
    pass


class KeyResponseError(Exception):
    """Исключение, возникающее при отсутствии ожидаемых ключей в ответе API"""
    
    pass