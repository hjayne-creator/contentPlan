web: gunicorn app:app
worker: celery -A celery_worker.celery worker --loglevel=debug 
