import os
import logging
from celery import Celery
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get Redis URL from environment
redis_url = os.environ.get('CELERY_BROKER_URL', '')
logger.info(f"Using Redis URL: {redis_url}")

# Initialize Celery with the same app name as the worker
celery = Celery('content_plan',  # Match the app name in celery_worker.py
                broker=redis_url,
                backend=redis_url)

# Configure Celery
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=100,
)

@celery.task
def simple_task():
    logger.info("Simple task started")
    time.sleep(2)
    logger.info("Simple task completed")
    return "Task completed successfully"

if __name__ == "__main__":
    logger.info("Starting simple Celery test...")
    
    try:
        # Send task
        logger.info("Sending task...")
        result = simple_task.delay()
        logger.info(f"Task ID: {result.id}")
        
        # Check task status with retries
        for i in range(5):
            status = result.status
            logger.info(f"Task status (attempt {i+1}): {status}")
            if status == 'SUCCESS':
                break
            time.sleep(2)
        
        # Try to get result
        logger.info("Attempting to get result...")
        task_result = result.get(timeout=10)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(f"Task status: {result.status if 'result' in locals() else 'Unknown'}")
    
    logger.info("Test completed.") 
