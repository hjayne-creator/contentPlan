from celery import Celery

# Initialize Celery
celery = Celery('content_plan',
                broker='redis://localhost:6379/0',
                backend='redis://localhost:6379/0')

# Optional configurations
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour timeout for tasks
    task_soft_time_limit=3300,  # Soft timeout 55 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
) 