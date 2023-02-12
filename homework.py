import logging
from logging.handlers import RotatingFileHandler
import telegram
from telegram import Bot
import os
import sys
import time
from http import HTTPStatus
from typing import Union
from exceptions import ParseStatusError
import json
import requests

from dotenv import load_dotenv 

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

def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат, 
    определяемый переменной окружения TELEGRAM_CHAT_ID."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        logging.DEBUG(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(error)

def get_api_answer(timestamp: int) -> Union[dict, str]:
    """Делает запрос к единственному эндпоинту API-сервиса.
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
    except Exception as error:
        logger.error(f'Ошибка запроса к API адресу: {error}')
    if response_from_api.status_code != HTTPStatus.OK:
        logger.error(
            f'Ошибка ответа от API адреса: {response_from_api.status_code}'
        )
        raise Exception(
            f'Ошибка ответа от API адреса: {response_from_api.status_code}'
        )
    try:
        response = response_from_api.json()
    except json.JSONDecodeError as error:
        logger.error(
            f'Ответ от API адреса не преобразован в json(): {error}.'
        )
    return response


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    if not response:
        message = 'В словаре нет данных.'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response, dict):
        message = 'В словаре некорректный тип данных.'
        logging.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'В словаре отсутствуют ожидаемые ключи.'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response.get('homeworks'), list):
        message = 'Формат ответа не соответствует искомому.'
        logging.error(message)
        raise TypeError(message)

    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Извлекает из информации о конкретной 
    домашней работе статус этой работы."""
    if not homework.get('homework_name'):
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
        raise ParseStatusError(message)

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус домашней работы'
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'

def check_tokens() -> bool:
    """Проверяет доступность переменных окружения,
    которые необходимы для работы программы."""
    list_env = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    return all(list_env)

def main():
    """Основная логика работы программы."""
    last_send = {
        'error': None,
    }
    if not check_tokens():
        logging.critical(
            f'''Отсутствует обязательная переменная окружения. 
            Работа программы остановлена.'''
        )
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
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
