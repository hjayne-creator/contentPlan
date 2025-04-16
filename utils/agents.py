import os
import json
import logging
from flask import current_app
from .openai_client import get_openai_client

def run_agent_with_openai(system_message, user_message, model=None):
    """
    Run a prompt using the OpenAI chat completions API.
    """
    try:
        # Get the model from config if not provided
        model = model or current_app.config.get('OPENAI_MODEL', current_app.config.get('OPENAI_MODEL_FALLBACK', 'gpt-4'))
        client = get_openai_client()

        logging.info(f"Calling OpenAI model: {model}")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        if response.choices:
            return response.choices[0].message.content.strip()

        raise Exception("OpenAI returned an empty response.")

    except Exception as e:
        logging.error(f"OpenAI API call failed: {e}", exc_info=True)
        raise  # Re-raise the exception instead of returning it as a string

