from starlite_bedrock.config import gunicorn_settings

# Gunicorn config variables
backlog = 2048
spew = False
accesslog = gunicorn_settings.ACCESS_LOG
bind = f"{gunicorn_settings.HOST}:{gunicorn_settings.PORT}"
errorlog = gunicorn_settings.ERROR_LOG
keepalive = gunicorn_settings.KEEPALIVE
loglevel = gunicorn_settings.LOG_LEVEL
reload = gunicorn_settings.RELOAD
threads = gunicorn_settings.THREADS
timeout = gunicorn_settings.TIMEOUT
worker_class = gunicorn_settings.WORKER_CLASS
workers = gunicorn_settings.WORKERS
preload = gunicorn_settings.PRELOAD
