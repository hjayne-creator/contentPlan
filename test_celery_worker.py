import os
import logging
from celery_worker import celery

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Log Celery configuration
    logger.info("Celery Configuration:")
    logger.info(f"Broker URL: {celery.conf.broker_url}")
    logger.info(f"Result Backend: {celery.conf.result_backend}")
    
    # Test sending a task
    @celery.task
    def test_task():
        logger.info("Test task started")
        return "Test task completed"
    
    try:
        logger.info("Sending test task...")
        result = test_task.delay()
        logger.info(f"Task ID: {result.id}")
        
        # Wait for result
        logger.info("Waiting for task result...")
        task_result = result.get(timeout=10)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Error in task execution: {str(e)}")

if __name__ == "__main__":
    logger.info("Starting Celery worker test...")
    main()
    logger.info("Test completed.") 
