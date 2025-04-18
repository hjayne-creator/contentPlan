web: gunicorn app:app
worker: celery -A celery_worker.celery worker --loglevel=debug --concurrency=4 --max-tasks-per-child=100 --max-memory-per-child=200000 -E 
