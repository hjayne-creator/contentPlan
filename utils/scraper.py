import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

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
    """Scrape website for meta title, meta description, and main body text (h1, h2, h3, p, li)."""
    try:
        if not validate_url(url):
            return {
                "success": False,
                "error": "Invalid URL format. Please include http:// or https://"
            }

        time.sleep(random.uniform(2, 5))
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
        session = create_session()
        response = session.get(
            url,
            headers=headers,
            timeout=30,
            verify=True,
            allow_redirects=True
        )
        if response.status_code == 403:
            return {"success": False, "error": "Access forbidden (403). The website might be blocking automated requests."}
        elif response.status_code == 429:
            return {"success": False, "error": "Too many requests (429). Please try again later."}
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return {"success": False, "error": f"Not an HTML page (Content-Type: {content_type})"}

        # Use correct encoding if possible
        if response.encoding:
            html = response.text
        else:
            response.encoding = response.apparent_encoding
            html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Remove navigation, footer, header, sidebar, and common boilerplate elements
        for selector in [
            "nav", "footer", "aside", "iframe", 
            ".menu", ".navbar", ".footer", ".sidebar", "#sidebar", "#nav", "#footer"
        ]:
            for element in soup.select(selector):
                element.extract()

        # Extract meta title
        title = ''
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        else:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()

        # Extract meta description
        description = ''
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc['content'].strip()
        else:
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                description = og_desc['content'].strip()

        # Extract h1, h2, h3, p, li tags in order of appearance
        body_elements = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = tag.get_text(separator=' ', strip=True)
            if text:
                body_elements.append(text)
        # Remove duplicate lines
        seen = set()
        unique_body = []
        for line in body_elements:
            if line not in seen:
                unique_body.append(line)
                seen.add(line)
        body_text = ' '.join(unique_body)
        # Clean up whitespace
        body_text = re.sub(r'\s+', ' ', body_text).strip()
        # Truncate to ~1000 words (8000 chars max)
        words = body_text.split()
        if len(words) > 1000:
            body_text = ' '.join(words[:1000]) + '... (truncated)'
        if len(body_text) > 8000:
            body_text = body_text[:8000] + '... (truncated)'

        # Lower minimum threshold for meaningful content
        if not (title or description or body_text):
            return {"success": False, "error": "No meaningful content extracted from the page."}
        if len(body_text) < 50:
            return {"success": False, "error": f"Insufficient content retrieved (only {len(body_text)} characters)"}

        return {
            "success": True,
            "title": title,
            "description": description,
            "body": body_text
        }
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.ConnectionError):
            return {"success": False, "error": f"Connection error - {str(e)}. The website might be blocking requests or experiencing issues."}
        elif isinstance(e, requests.exceptions.Timeout):
            return {"success": False, "error": f"Request timed out - {str(e)}"}
        elif isinstance(e, requests.exceptions.SSLError):
            return {"success": False, "error": f"SSL error - {str(e)}"}
        else:
            return {"success": False, "error": f"Request failed - {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
