from celery_worker import celery
import time

@celery.task
def simple_test():
    print("Starting simple test task...")
    time.sleep(2)
    print("Test task completed!")
    return "Test successful!"

if __name__ == "__main__":
    # Send the task
    result = simple_test.delay()
    print(f"Task ID: {result.id}")
    
    # Wait for the result
    print("Waiting for task to complete...")
    task_result = result.get(timeout=10)
    print(f"Task result: {task_result}") 
