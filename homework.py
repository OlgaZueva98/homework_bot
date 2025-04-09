import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

from exceptions import StatusError


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

MAX_LOG_SIZE = 50000000

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Токены необходимые для работы программы
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN')

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s %(name)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing_tokens = [token for token in TOKENS
                      if globals()[token] is None or globals()[token] == '']

    if missing_tokens:
        error = (
            'Отсутствуют переменные окружения:',
            f'{", ".join(missing_tokens)}'
        )
        logger.critical(error)
        raise ValueError(error)


def send_message(bot, message):
    """Отправляет сообщения в Telegram-чат."""
    logger.debug('Начало работы.')

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}

    logger.debug(f'Запрос к {ENDPOINT} с параметрами {HEADERS}, {payload}')

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )

    except requests.RequestException as error:
        error_message = f'Произошла ошибка: {error}.'
        raise ConnectionError(error_message)

    if response.status_code != HTTPStatus.OK:
        error_message = f'Запрос завершился с кодом: {response.status_code}.'
        raise StatusError(error_message)

    logger.debug('Ответ успешно получен.')

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Начало проверки.')

    if not isinstance(response, dict):
        error = (
            'Тип данных не соответствует ожидаемому формату.',
            f'Полученный: {type(response)}.',
            'Ожидаемый: dict.'
        )
        logger.error(error)
        raise TypeError(error)

    if 'homeworks' not in response:
        error = 'Отсутствует ключ со списком домашних работ.'
        logger.error(error)
        raise KeyError(error)

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        error = (
            'Значение ключа homeworks не соответствует ожидаемому формату.'
            f'Полученный: {type(homeworks)}.',
            'Ожидаемый: list.'
        )
        logger.error(error)
        raise TypeError(error)

    logger.debug('Проверка завершена успешно.')

    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    logger.debug('Начинало парсинга.')

    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)

    missing_keys = [key for key in (homework_name, status) if key is None]
    if missing_keys:
        error = f'Отсутствуют ключи: {", ".join(missing_keys)}.'
        logger.error(error)
        raise KeyError(error)

    if verdict is None:
        error = f'Статус отсутствует в HOMEWORKS_VERDICTS. Статус: {verdict}.'
        logger.error(error)
        raise ValueError(error)

    logger.debug('Извлечена информация о домашней работе.')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('Нет изменений.')

                continue

            message = parse_status(homeworks[0])
            if message != previous_message:
                send_message(bot, message)
                previous_message == message

            timestamp = response.get('current_date', timestamp)

        except apihelper.ApiException or requests.exceptions.RequestException:
            logger.error('Сбой в телеграм.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message == message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
