import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot


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

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    f'{__file__}.log',
    maxBytes=MAX_LOG_SIZE,
    encoding='utf-8'
)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s %(name)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)):
        error = 'Отсутствуют переменные окружения.'
        logger.critical(error)
        raise SystemExit(error)


def send_message(bot, message):
    """Отправляет сообщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено.')

    except Exception as error:
        logger.error(
            f'Произошла ошибка: {error}.'
        )


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )

    except requests.ConnectionError as error:
        logger.error(
            f'Ошибка соединения: {error}.'
        )
        raise ConnectionError

    except requests.RequestException as error:
        error_message = f'Произошла ошибка: {error}.'
        logger.error(error_message)
        raise Exception(error_message)

    if response.status_code != HTTPStatus.OK:
        error_message = f'Запрос завершился с кодом: {response.status_code}.'
        logger.error(error_message)
        raise Exception(error_message)

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        error = 'Ответ не соответствует формату json.'
        logger.error(error)
        raise TypeError(error)

    homeworks = response.get('homeworks')

    if homeworks is None:
        error = 'Отсутствует ключ со списком домашних работ.'
        logger.error(error)
        raise KeyError(error)

    if not isinstance(homeworks, list):
        error = 'Значение ключа homeworks не является списком.'
        logger.error(error)
        raise TypeError(error)

    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)

    if homework_name is None:
        error = 'Отсутствует ключ homework_name.'
        logger.error(error)
        raise KeyError(error)

    if status is None:
        error = 'Отсутствует ключ status.'
        logger.error(error)
        raise KeyError(error)

    if verdict is None:
        error = 'Статус отсутствует в HOMEWORKS_VERDICTS.'
        logger.error(error)
        raise KeyError(error)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('Нет изменений.')

            message = parse_status(homeworks[0])
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
