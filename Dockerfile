FROM tiangolo/uwsgi-nginx-flask:python3.9

ENV STATIC_INDEX 1

COPY ./app /app

