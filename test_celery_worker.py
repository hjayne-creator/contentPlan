import os
import logging
import redis
from celery_worker import celery
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection directly"""
    redis_url = os.environ.get('CELERY_BROKER_URL', '')
    logger.info(f"Testing Redis connection with URL: {redis_url}")
    
    try:
        r = redis.from_url(redis_url)
        r.ping()
        logger.info("Redis connection successful!")
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

def main():
    # Test Redis connection first
    if not test_redis_connection():
        logger.error("Cannot proceed without Redis connection")
        return

    # Log environment variables
    logger.info("\nEnvironment Variables:")
    logger.info(f"CELERY_BROKER_URL: {os.environ.get('CELERY_BROKER_URL')}")
    logger.info(f"CELERY_RESULT_BACKEND: {os.environ.get('CELERY_RESULT_BACKEND')}")
    
    # Log Celery configuration
    logger.info("\nCelery Configuration:")
    logger.info(f"Broker URL: {celery.conf.broker_url}")
    logger.info(f"Result Backend: {celery.conf.result_backend}")
    logger.info(f"Task Serializer: {celery.conf.task_serializer}")
    logger.info(f"Accept Content: {celery.conf.accept_content}")
    
    # Test sending a task
    @celery.task
    def test_task():
        logger.info("Test task started")
        time.sleep(2)  # Simulate some work
        logger.info("Test task completed")
        return "Test task completed"
    
    try:
        logger.info("\nSending test task...")
        result = test_task.delay()
        logger.info(f"Task ID: {result.id}")
        
        # Check task status with retries
        for i in range(5):
            status = result.status
            logger.info(f"Task status (attempt {i+1}): {status}")
            if status == 'SUCCESS':
                break
            time.sleep(2)
        
        # Try to get result
        logger.info("\nAttempting to get task result...")
        task_result = result.get(timeout=10)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Error in task execution: {str(e)}")
        logger.error(f"Task status: {result.status if 'result' in locals() else 'Unknown'}")

if __name__ == "__main__":
    logger.info("Starting Celery worker test...")
    main()
    logger.info("Test completed.") 
