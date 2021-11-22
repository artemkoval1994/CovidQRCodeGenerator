import base64
import io
import os
import random
import string
import uuid
from datetime import timedelta, datetime
from urllib.parse import urlparse

import idna
import pytz
import redis
from pyqrcode import QRCode
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_url = urlparse(redis_url)

redis_client = redis.Redis(host=redis_url.hostname, port=redis_url.port, db=redis_url.path[1:])

users = {}
if os.getenv('ADMIN_USERS') and int(os.getenv('ADMIN_USERS')) > 0:
    for idx in range(int(os.getenv('ADMIN_USERS'))):
        users[os.getenv(f'USER_{idx}_TG_CHAT_ID')] = {
            'first_name': os.getenv(f'USER_{idx}_FIRST_NAME'),
            'last_name': os.getenv(f'USER_{idx}_LAST_NAME'),
            'second_name': os.getenv(f'USER_{idx}_SECOND_NAME'),
            'b_day': os.getenv(f'USER_{idx}_B_DAY'),
            'series': os.getenv(f'USER_{idx}_SERIES'),
            'number': os.getenv(f'USER_{idx}_NUMBER'),
            'timezone': os.getenv(f'USER_{idx}_TIMEZONE'),
        }


def start(update: Update, context: CallbackContext) -> None:
    if str(update.effective_chat.id) in users:
        user = users[str(update.effective_chat.id)]
        keyword = [
            [
                InlineKeyboardButton('Всё верно!', callback_data='passport_yes'),
                InlineKeyboardButton('Не то!', callback_data='passport_no')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyword)
        update.message.reply_html(
            (
                'Подтвердите правильность данных:\n\n'
                'ФИО: <b>{} {} {}</b>\n'
                'День рождения: <b>{}</b>\n'
                'Серия и номер паспорта: <b>{}** ***{}</b>'.format(
                    user['last_name'], user['first_name'], user['second_name'],
                    user['b_day'],
                    user['series'], user['number']
                )
            ),
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            f'{update.effective_user.first_name}, извиняйте, но вашего ID ({update.effective_chat.id}) нет в системе.'
        )


def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'passport_yes':
        keyboard = [
            [InlineKeyboardButton('1 час', callback_data='3600')],
            [InlineKeyboardButton('30 минут', callback_data='1800')],
            [InlineKeyboardButton('10 минут', callback_data='600')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text('На какой период времени создать QR-код?', reply_markup=reply_markup)
    elif query.data == 'passport_no':
        query.edit_message_text('Пока нет возможности исправлять данные паспорта через Telegram бота.')
    elif query.data in ['3600', '1800', '600']:
        url = os.getenv('TG_BOT_QR_HOST')
        try:
            url = idna.encode(url).decode('utf-8')
        except idna.core.InvalidCodepoint:
            pass
        unrz = ''.join(random.choice(string.digits) for _ in range(16))
        ck = uuid.uuid4().hex.replace('-', '')
        url = 'https://{}/covid-cert/verify/{}?lang=ru&ck={}'.format(
            url,
            unrz,
            ck
        )
        qr = QRCode(url)
        media = io.BytesIO()
        qr.png(media, scale=4)
        user = users[str(query.message.chat_id)]
        qr_code = media.getvalue()
        qr_config = user
        qr_config['qr'] = base64.b64encode(qr_code).decode('utf-8')
        for key, value in qr_config.items():
            redis_client.hset(unrz, key, value)
        redis_client.expire(unrz, timedelta(seconds=int(query.data)))
        user_datetime = datetime.now(pytz.timezone(user['timezone'])) + timedelta(seconds=int(query.data))
        caption = 'Этот QR-код надо сохранить в фото.\n\nКод действителен до: {}'.format(
            user_datetime.strftime('%H:%M:%S %d.%m.%Y (%Z)')
        )
        query.delete_message()
        query.message.reply_photo(photo=qr_code, caption=caption)


def main() -> None:
    updater = Updater(os.getenv('TG_BOT_TOKEN'))

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
