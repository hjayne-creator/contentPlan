from celery_worker import celery
import time
import redis
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test Redis connection
redis_url = os.environ.get('CELERY_BROKER_URL', '')
logger.info(f"Testing Redis connection with URL: {redis_url}")

try:
    r = redis.from_url(redis_url)
    r.ping()
    logger.info("Redis connection successful!")
except Exception as e:
    logger.error(f"Redis connection failed: {str(e)}")

@celery.task
def simple_test():
    logger.info("Starting simple test task...")
    time.sleep(2)
    logger.info("Test task completed!")
    return "Test successful!"

if __name__ == "__main__":
    # Send the task
    result = simple_test.delay()
    logger.info(f"Task ID: {result.id}")
    
    # Wait for the result
    logger.info("Waiting for task to complete...")
    try:
        task_result = result.get(timeout=10)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Error getting task result: {str(e)}") 
