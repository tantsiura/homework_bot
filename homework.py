import logging
from logging.handlers import RotatingFileHandler
import telegram
import requests
import os
import sys
import time
from http import HTTPStatus
from typing import Union
import exceptions
import json

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout

)

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

handler.setFormatter(formatter)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    environment_variables = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    return all(environment_variables)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка отправки сообщения в телеграм {error}')
    else:
        logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp: int) -> Union[dict, str]:
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    Осуществляет запрос к эндпоинту API-сервиса. В качестве параметра
    функция получает временную метку. В случае успешного запроса должна
    вернуть ответ API, преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
        response_from_api = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except requests.RequestException as error:
        message = f'Ошибка запроса к API адресу: {error}'
        logging.error(message)
        raise exceptions.EndpointIsUnavailable
    if response_from_api.status_code != HTTPStatus.OK:
        message = (f'''
        Ошибка ответа от API адреса: {response_from_api.status_code}
        ''')
        logger.error(message)
        raise exceptions.HttpStatusCodeError
    try:
        response = response_from_api.json()
    except json.JSONDecodeError as error:
        message = f'Ответ от API адреса не преобразован в json(): {error}.'
        logger.error(message)
        raise exceptions.JsonApiError
    return response


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    if not response:
        message = 'В словаре нет данных.'
        logging.error(message)
        raise exceptions.EmptyResponseError

    if not isinstance(response, dict):
        message = 'В словаре некорректный тип данных.'
        logging.error(message)
        raise TypeError

    if 'homeworks' not in response:
        message = 'В словаре отсутствуют ожидаемые ключи.'
        logging.error(message)
        raise exceptions.KeyResponseError
    homework = response['homeworks']
    if not isinstance(homework, list):
        message = 'Формат ответа не соответствует искомому.'
        logging.error(message)
        raise TypeError

    return homework


def parse_status(homework: dict) -> str:
    """Извлекает из статус домашней работы."""
    if 'homework_name' not in homework:
        homework_name = 'NoName'
        logging.warning('Отсутствует имя домашней работы.')
        raise KeyError('В ответе API отсутствует '
                       'ожидаемый ключ "homework_name".')
    else:
        homework_name = homework.get('homework_name')

    homework_status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсутстует ключ homework_status.'
        logging.error(message)
        raise exceptions.ParseStatusError(message)
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус домашней работы'
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    last_send = {
        'error': None,
    }
    if not check_tokens():
        logging.critical(
            'Отсутствует обязательная переменная окружения.'
            'Работа программы остановлена.')
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Ответ API пуст: нет домашних работ.')
                break
            for homework in homeworks:
                message = parse_status(homework)
                if last_send.get(homework['homework_name']) != message:
                    send_message(bot, message)
                    last_send[homework['homework_name']] = message
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_send['error'] != message:
                send_message(bot, message)
                last_send['error'] = message
        else:
            last_send['error'] = None
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
