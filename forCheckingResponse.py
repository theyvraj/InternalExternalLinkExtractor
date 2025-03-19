from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_captcha_url(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Look for the CAPTCHA image in the HTML
    # Example: Find an <img> tag with a specific class or id
    captcha_img_tag = soup.find('img', {'class': 'captcha-image'})  # Adjust the attribute as needed

    if captcha_img_tag:
        captcha_url = captcha_img_tag['src']
        # Ensure we create a full URL if the src is relative
        return urljoin("https://business-directory-local.com", captcha_url)
    
    return None