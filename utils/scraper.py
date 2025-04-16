import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def validate_url(url):
    """Validate if the given string is a proper URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def scrape_website(url):
    """Scrape website content using BeautifulSoup."""
    try:
        # Validate URL format
        if not validate_url(url):
            return f"Error scraping website: Invalid URL format. Please include http:// or https://"
        
        # Set headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Make the request with a timeout
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return f"Error scraping website: Not an HTML page (Content-Type: {content_type})"
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, nav, footer, header elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            element.extract()
            
        # Get the main content - prefer articles or main elements if they exist
        main_content = None
        
        # Try to find main content containers
        for container in ['article', 'main', '.content', '#content', '.main', '#main']:
            if container.startswith('.') or container.startswith('#'):
                selector = container
            else:
                selector = container
            
            elements = soup.select(selector)
            if elements:
                main_content = ' '.join([elem.get_text(separator=' ', strip=True) for elem in elements])
                break
        
        # If no specific content container found, use the body
        if not main_content:
            main_content = soup.body.get_text(separator=' ', strip=True) if soup.body else ''
        
        # If still empty, use the entire document
        if not main_content:
            main_content = soup.get_text(separator=' ', strip=True)
            
        # Clean up text (remove extra whitespace)
        clean_text = re.sub(r'\s+', ' ', main_content).strip()
        
        # Check if we got meaningful content
        if len(clean_text) < 100:
            return f"Error scraping website: Insufficient content retrieved (only {len(clean_text)} characters)"
        
        return clean_text
    
    except requests.exceptions.RequestException as e:
        return f"Error scraping website: Request failed - {str(e)}"
    except Exception as e:
        return f"Error scraping website: {str(e)}"