from openai import OpenAI
import os
from dotenv import load_dotenv

def test_openai_connection():
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return
    
    try:
        # Initialize the client
        client = OpenAI(api_key=api_key)
        
        # Make a simple test call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using a simpler model for testing
            messages=[
                {"role": "user", "content": "Say 'Hello, test successful!'"}
            ]
        )
        
        # Print the response
        print("API Response:", response.choices[0].message.content)
        print("Test successful!")
        
    except Exception as e:
        print(f"Error testing OpenAI API: {str(e)}")

if __name__ == "__main__":
    test_openai_connection() 