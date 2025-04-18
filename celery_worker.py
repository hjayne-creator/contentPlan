from app import app
from celery_config import celery
import os
import logging
import redis
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask application context
app.app_context().push()

# Log Redis connection details (without exposing sensitive information)
redis_url = os.environ.get('CELERY_BROKER_URL', '')
if redis_url:
    parsed_url = urlparse(redis_url)
    logger.info(f"Redis host: {parsed_url.hostname}")
    logger.info(f"Redis port: {parsed_url.port}")
    logger.info(f"Redis database: {parsed_url.path}")

# Test Redis connection
try:
    if redis_url:
        r = redis.from_url(redis_url)
        r.ping()
        logger.info("Successfully connected to Redis")
    else:
        logger.error("CELERY_BROKER_URL not set in environment variables")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
except Exception as e:
    logger.error(f"Unexpected error testing Redis connection: {str(e)}")

# Ensure configuration is loaded
if not app.config.get('OPENAI_API_KEY'):
    app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY')
if not app.config.get('SERPAPI_API_KEY'):
    app.config['SERPAPI_API_KEY'] = os.environ.get('SERPAPI_API_KEY')

logger.info("Initializing Celery worker with configuration:")
logger.info(f"OPENAI_API_KEY set: {bool(app.config.get('OPENAI_API_KEY'))}")
logger.info(f"SERPAPI_API_KEY set: {bool(app.config.get('SERPAPI_API_KEY'))}")
logger.info(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

# Configure Celery to use the same Flask app context
def celery_init_app(app):
    class FlaskTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask
    return celery

# Initialize Celery with Flask context
celery = celery_init_app(app)

if __name__ == '__main__':
    logger.info("Starting Celery worker...")
    celery.worker_main(['worker', '--loglevel=debug']) 
