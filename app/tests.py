import os
import random
import string
from datetime import timedelta

import unittest
import main as tested_app


class FlaskAppTest(unittest.TestCase):
    def setUp(self) -> None:
        tested_app.app.config['TESTING'] = True
        self.app = tested_app.app.test_client()
        setattr(self.app, 'users', tested_app.users)
        self.redis_client = tested_app.redis_client

    def test_get_home(self):
        r = self.app.get('/')
        self.assertEqual(r.status_code, 302)

    def test_get_covid_cert_verify_fail(self):
        unrz = self.get_unrz()
        r = self.app.get(f'/covid-cert/verify/{unrz}')
        self.assertEqual(r.status_code, 302)

    def test_get_covid_cert_verify(self):
        unrz = self.get_unrz(write_to_redis=True)
        r = self.app.get(f'/covid-cert/verify/{unrz}')
        self.assertEqual(r.status_code, 200)

    def test_get_covid_confid(self):
        r = self.app.get('/covid-web/config.json')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.is_json, True)

        data = r.json
        self.assertEqual(data['covidCertCheckUrl'], '/api/covid-cert/v3/cert/check/')

    def test_get_covid_cert_check_fail(self):
        unrz = self.get_unrz()
        r = self.app.get(f'/api/covid-cert/v3/cert/check/{unrz}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.is_json, True)
        self.assertEqual(r.json, {})

    def test_get_covid_cert_check(self):
        unrz = self.get_unrz(write_to_redis=True)
        r = self.app.get(f'/api/covid-cert/v3/cert/check/{unrz}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.is_json, True)

        data = r.json['items'][0]
        self.assertEqual(data['unrzFull'], unrz)
        self.assertEqual(data['qr'], '')

    def get_unrz(self, write_to_redis=False):
        unrz = ''.join(random.choice(string.digits) for _ in range(16))

        if write_to_redis:
            data: dict = self.app.users['admin']
            data['qr'] = ''
            for key, value in data.items():
                self.redis_client.hset(unrz, key, value)
            self.redis_client.expire(unrz, timedelta(seconds=10))

        return unrz


if __name__ == '__main__':
    unittest.main()
