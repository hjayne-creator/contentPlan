import os
import time
import redis
import logging
from celery_worker import celery

# Configure logging to show all output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Test Redis connection
    redis_url = os.environ.get('CELERY_BROKER_URL', '')
    logger.info(f"Testing Redis connection with URL: {redis_url}")
    
    try:
        r = redis.from_url(redis_url)
        r.ping()
        logger.info("Redis connection successful!")
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return

    # Test Celery task
    @celery.task
    def simple_test():
        logger.info("Starting simple test task...")
        time.sleep(2)
        logger.info("Test task completed!")
        return "Test successful!"

    try:
        # Send the task
        logger.info("Sending test task...")
        result = simple_test.delay()
        logger.info(f"Task ID: {result.id}")
        
        # Wait for the result
        logger.info("Waiting for task to complete...")
        task_result = result.get(timeout=10)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Error in task execution: {str(e)}")

if __name__ == "__main__":
    logger.info("Starting Celery test...")
    main()
    logger.info("Test completed.") 
