import os
from celery import Celery
from celery.signals import after_setup_logger

# Initialize Celery using environment variables from Render
celery = Celery(
    'content_plan',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

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
    broker_connection_retry_on_startup=True,  # Enable connection retry on startup
    broker_connection_max_retries=10,  # Maximum number of retries
    broker_connection_retry_delay=5,  # Delay between retries in seconds
    broker_heartbeat=10,  # Heartbeat interval in seconds
    broker_pool_limit=10,  # Maximum number of connections in the pool
)

@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """Configure logging for Celery"""
    import logging
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
