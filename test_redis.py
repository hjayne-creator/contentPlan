import os
import redis
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get Redis URL
redis_url = os.environ.get('CELERY_BROKER_URL', '')
logger.info(f"Testing Redis connection with URL: {redis_url}")

try:
    # Test Redis connection
    r = redis.from_url(redis_url)
    r.ping()
    logger.info("Redis connection successful!")
    
    # Test setting and getting a value
    r.set('test_key', 'test_value')
    value = r.get('test_key')
    logger.info(f"Test value retrieved: {value}")
    
except Exception as e:
    logger.error(f"Redis test failed: {str(e)}") 
