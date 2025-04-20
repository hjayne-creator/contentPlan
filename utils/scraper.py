import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def validate_url(url):
    """Validate if the given string is a proper URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_random_user_agent():
    """Return a random modern browser user agent."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15'
    ]
    return random.choice(user_agents)

def create_session():
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # increased number of retries
        backoff_factor=2,  # increased backoff time
        status_forcelist=[500, 502, 503, 504, 429, 403, 408],
        allowed_methods=["GET", "POST", "HEAD", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def scrape_website(url):
    """Scrape website content using BeautifulSoup."""
    try:
        # Validate URL format
        if not validate_url(url):
            return f"Error scraping website: Invalid URL format. Please include http:// or https://"
        
        # Add a random delay between 2-5 seconds
        time.sleep(random.uniform(2, 5))
        
        # Set headers to mimic a modern browser
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        # Create a session with retry logic
        session = create_session()
        
        # Make the request with a longer timeout
        response = session.get(
            url, 
            headers=headers, 
            timeout=30,  # increased timeout
            verify=True,  # verify SSL certificates
            allow_redirects=True  # follow redirects
        )
        
        # Check response status
        if response.status_code == 403:
            return "Error scraping website: Access forbidden (403). The website might be blocking automated requests."
        elif response.status_code == 429:
            return "Error scraping website: Too many requests (429). Please try again later."
        
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return f"Error scraping website: Not an HTML page (Content-Type: {content_type})"
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, nav, footer, header elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.extract()
            
        # Get the main content - prefer articles or main elements if they exist
        main_content = None
        
        # Try to find main content containers
        for container in ['article', 'main', '.content', '#content', '.main', '#main', '.article', '.post']:
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
        if isinstance(e, requests.exceptions.ConnectionError):
            return f"Error scraping website: Connection error - {str(e)}. The website might be blocking requests or experiencing issues."
        elif isinstance(e, requests.exceptions.Timeout):
            return f"Error scraping website: Request timed out - {str(e)}"
        elif isinstance(e, requests.exceptions.SSLError):
            return f"Error scraping website: SSL error - {str(e)}"
        else:
            return f"Error scraping website: Request failed - {str(e)}"
    except Exception as e:
        return f"Error scraping website: {str(e)}"
