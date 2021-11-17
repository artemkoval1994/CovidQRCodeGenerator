import base64
import io
import os
import random
import secrets
import string
import uuid
from datetime import timedelta, datetime
from urllib.parse import urljoin

import idna
from flask import Flask, request, send_file, render_template, redirect, url_for
from flask_httpauth import HTTPDigestAuth
from flask_redis import FlaskRedis
from fakeredis import FakeRedis
from pyqrcode import QRCode
from transliterate import translit
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
auth = HTTPDigestAuth()
if app.testing:
    redis_client = FakeRedis(app)
else:
    redis_client = FlaskRedis(app)

users = {
    'admin': {
        'password': 'password',
        'first_name': 'Иван',
        'last_name': 'Иванов',
        'second_name': 'Иванович',
        'b_day': '2020-01-01',
        'series': '12',
        'number': '789',
    }
}
if app.config.get('ADMIN_USERS') and int(app.config.get('ADMIN_USERS')) > 0:
    users = {}
    for idx in range(int(app.config['ADMIN_USERS'])):
        users[app.config.get(f'USER_{idx}_USERNAME')] = {
            'password': app.config.get(f'USER_{idx}_PASSWORD'),
            'first_name': app.config.get(f'USER_{idx}_FIRST_NAME'),
            'last_name': app.config.get(f'USER_{idx}_LAST_NAME'),
            'second_name': app.config.get(f'USER_{idx}_SECOND_NAME'),
            'b_day': app.config.get(f'USER_{idx}_B_DAY'),
            'series': app.config.get(f'USER_{idx}_SERIES'),
            'number': app.config.get(f'USER_{idx}_NUMBER'),
        }
setattr(app, 'users', users)


@auth.get_password
def get_pw(username):
    if username in users:
        return users[username]['password']
    return None


@app.route('/')
def home():
    return redirect('https://www.gosuslugi.ru', code=302)


@app.route('/covid-cert/verify/<string:unrz>')
def covid_cert_verify(unrz: str):
    if not redis_client.exists(unrz):
        query = request.query_string.decode('utf-8').replace("'", '')
        real_url_check = f'https://www.gosuslugi.ru/covid-cert/verify/{unrz}?{query}'
        return redirect(real_url_check)
    return render_template('covid-cert.html', unrz=unrz)


@app.route('/covid-web/config.json')
def covid_config():
    return {
        "production": True,
        "baseUrl": "https://www.gosuslugi.ru/",
        "betaUrl": "https://www.gosuslugi.ru/",
        "lkUrl": "https://lk.gosuslugi.ru/",
        "lkApiUrl": "//www.gosuslugi.ru/api/lk/v1/",
        "yaCounter": 0,
        "authProviderUrl": "//www.gosuslugi.ru/auth-provider/login?rUrl=",
        "nsiApiUrl": "//www.gosuslugi.ru/api/nsi/v1/",
        "staticDomainLibAssetsPath": "//gu-st.ru/covid-web-st/lib-assets/",
        "timingApiUrl": "//www.gosuslugi.ru/health",
        "staticDomainAssetsPath": "//gu-st.ru/covid-web-st/assets/",
        "appStores": {
            "appStore": "https://redirect.appmetrica.yandex.com/serve/529060629282032912",
            "googlePlay": "https://redirect.appmetrica.yandex.com/serve/745233407570662167",
            "appGallery": "https://appgallery8.huawei.com/#/app/C101280309"
        },
        "socialNetworks": {
            "vk": "https://vk.me/new.gosuslugi",
            "ok": "https://ok.ru/gosuslugi",
            "fb": "https://www.facebook.com/new.gosuslugi",
            "tg": "https://t.me/gosuslugi"
        },
        "portalCfgUrl": "//www.gosuslugi.ru/api/portal-cfg/",
        "mainBlocksData": "//www.gosuslugi.ru/api/mainpage/v4",
        # "covidCertCheckUrl": "//www.gosuslugi.ru/api/covid-cert/v3/cert/check/",
        "covidCertCheckUrl": "/api/covid-cert/v3/cert/check/",
        "covidCertUrl": "//www.gosuslugi.ru/api/covid-cert/v2/",
        "registerCovidUrl": "//www.gosuslugi.ru/api/register-covid/v2/",
        "vaccineUrl": "//www.gosuslugi.ru/api/vaccine/v1/",
        "covidCertPdfUrl": "//www.gosuslugi.ru/api/covid-cert/v1/cert/{unrzFull}/pgu/srfile/pdf",
        "vaccineUrlv2": "//www.gosuslugi.ru/api/vaccine/v2/",
        "quadrupelUrl": "//www.gosuslugi.ru/api/quadrupel/v1/",
        "grpIdCheck": ["RA.USR_CFM", "RA_TOOL_SUPERACCESS"]
    }


@app.route('/api/covid-cert/v3/cert/check/<string:unrz>')
def covid_cert_check(unrz: str):
    if not redis_client.exists(unrz):
        return {}

    config = redis_client.hgetall(unrz)
    config = {x.decode('utf-8'): config.get(x).decode('utf-8') for x in config}

    en_first_name = translit(config['first_name'], 'ru', reversed=True)
    en_last_name = translit(config['last_name'], 'ru', reversed=True)
    en_second_name = translit(config['second_name'], 'ru', reversed=True)

    fio = [
        '{} {} {}'.format(
            config['last_name'][0] + '*' * (len(config['last_name']) - 1),
            config['first_name'][0] + '*' * (len(config['first_name']) - 1),
            config['second_name'][0] + '*' * (len(config['second_name']) - 1),
        ),
        '{} {} {}'.format(
            en_last_name[0] + '*' * (len(en_last_name) - 1),
            en_first_name[0] + '*' * (len(en_first_name) - 1),
            en_second_name[0] + '*' * (len(en_second_name) - 1),
        ),
    ]

    b_day = datetime.strptime(config['b_day'], '%Y-%m-%d')

    recovery_date = datetime.now() - relativedelta(months=2)
    valid_until = recovery_date + relativedelta(months=6)

    return dict({
        'items': [
            {
                'type': 'ILLNESS_FACT',
                'unrz': '123123132',
                'unrzFull': unrz,
                'attrs': [
                    {
                        'type': 'date',
                        'title': 'Дата выздоровления',
                        'entitle': 'Recovery date',
                        'envalue': recovery_date.strftime('%d.%m.%Y'),
                        'value': recovery_date.strftime('%d.%m.%Y'),
                        'order': 1,
                    },
                    {
                        'type': 'date',
                        'title': 'Действует до',
                        'entitle': 'Valid until',
                        'envalue': valid_until.strftime('%d.%m.%Y'),
                        'value': valid_until.strftime('%d.%m.%Y'),
                        'order': 1,
                    },
                    {
                        'type': 'fio',
                        'title': 'ФИО',
                        'entitle': 'Full name',
                        'envalue': fio[1],
                        'value': fio[0],
                        'order': 3,
                    },
                    {
                        'type': 'passport',
                        'title': 'Паспорт',
                        'entitle': 'National passport',
                        'envalue': '{}** ***{}'.format(config['series'], config['number']),
                        'value': '{}** ***{}'.format(config['series'], config['number']),
                        'order': 4,
                    },
                    {
                        'type': 'birthDate',
                        'title': 'Дата рождения',
                        'entitle': 'Date of birth',
                        'envalue': b_day.strftime('%d.%m.%Y'),
                        'value': b_day.strftime('%d.%m.%Y'),
                        'order': 6,
                    },
                ],
                'title': 'Сведения о перенесенном заболевании COVID-19',
                'entitle': 'Previous disease COVID-19',
                'qr': config['qr'],
                'status': '1',
                'order': 0,
                'expiredAt': valid_until.strftime('%d.%m.%Y'),
                'serviceUnavailable': False,
            }
        ],
        'hasNext': False,
    })


@app.route('/qr-gen', methods=['GET', 'POST'])
@auth.login_required
def qr_generator():
    qr_code = None
    url = None

    if request.method == 'POST':
        # Генерируем случайный код пациента
        unrz = ''.join(random.choice(string.digits) for x in range(16))
        # Генерируем случайный код проверки
        ck = uuid.uuid4().hex.replace('-', '')
        # Указываем язык по умолчанию
        lang = 'ru'
        # Создает query параметры для URL
        query_params = f'{lang=}&{ck=}'
        # Создаём URL для будущего QR-кода
        host = idna.encode(request.host)
        host = 'https://{}/'.format(host.decode('utf-8'))
        url = urljoin(host, url_for('covid_cert_verify', unrz=unrz))
        url += '?' + query_params.replace("'", '')

        # Создаём необходимый нам QR-код
        qr = QRCode(url)
        buffer = io.BytesIO()
        qr.png(buffer, scale=4)
        qr_code = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Получаем данные из формы и записываем в Redis с указанным сроком годности
        qr_config = request.form.to_dict()
        qr_config['qr'] = qr_code
        for key, value in qr_config.items():
            redis_client.hset(unrz, key, value)
        redis_client.expire(unrz, timedelta(seconds=int(qr_config.get('expire', 3600))))

    return render_template('qr-generator.html',
                           username=auth.current_user(),
                           user=users[auth.current_user()],
                           url=url, qr_code=qr_code)


@app.route('/<path:path>')
def route_frontend(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_file(file_path)
    else:
        return redirect('https://www.gosuslugi.ru')


if __name__ == '__main__':
    app.run()
