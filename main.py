import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os
import json
def normalize_url(url):
    if url.endswith('/'):
        url = url[:-1]
    return url

def check_url(start_url, current_url):
    start_netloc = urllib.parse.urlparse(start_url).netloc
    current_netloc = urllib.parse.urlparse(current_url).netloc
    return start_netloc == current_netloc

def get_img_data(soup, domain):
    total_images = 0
    images_with_alt = 0
    images_without_alt = 0
    images_without_alt_details = []    
    for img in soup.find_all('img'):
        total_images += 1
        img_src = img.get('src', '')
        if img_src:
            if not img.get('alt') or img.get('alt').strip() == '':
                images_without_alt += 1
                images_without_alt_details.append("url: " +img_src + "\n")
            else:
                images_with_alt += 1
    alt_text_analysis = {
        "missing_alt_text": images_without_alt,
        "message": f"We found {total_images} images on your page, and {images_without_alt} of them are missing the alt attribute.",
        "images_without_alt_details": images_without_alt_details
    }    
    images_data = {
        "total_images": total_images,
        "images_with_alt": images_with_alt,
        "images_without_alt": images_without_alt,
        "alt_text_analysis": alt_text_analysis
    }    
    return images_data

def get_link_data(soup, domain, url):
    internal_links = set()
    external_links = set()
    broken_links = set()
    links_in_page = set()    
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if '#' in href:
            continue            
        anchor_text = link.get_text().strip() or "N/A"
        full_url = urllib.parse.urljoin(domain, href)
        full_url = normalize_url(full_url)
        try:
            head_response = requests.head(full_url, timeout=5)
            if head_response.status_code >= 400:
                broken_links.add((full_url, anchor_text, url))
        except requests.RequestException:
            broken_links.add((full_url, anchor_text, url))
            
        if domain in full_url:
            internal_links.add((full_url, anchor_text, url))
            links_in_page.add(full_url)
        else:
            external_links.add((full_url, anchor_text, url))
    return internal_links, external_links, broken_links, links_in_page

def get_head_data(soup):
    meta_title = {"content": "", "valid": False, "errors": [], "warnings": [], "length": 0}
    meta_description = {"content": "", "valid": False, "errors": [], "warnings": [], "length": 0}    
    head_tag = soup.find('head')
    if head_tag:
        title = head_tag.find('title')
        if title and title.get_text().strip():
            title_text = title.get_text().strip()
            meta_title["content"] = title_text
            meta_title["valid"] = True
            meta_title["length"] = len(title_text)
            if len(title_text) < 30:
                meta_title["warnings"].append("Meta title is too short (< 30 characters)")
            elif len(title_text) > 65:
                meta_title["warnings"].append("Meta title is too long (> 60 characters)")
        else:
            meta_title["errors"].append("Meta title is missing")
        meta_desc = head_tag.find('meta', attrs={"name": "description"})
        if meta_desc and meta_desc.get('content', '').strip():
            desc_text = meta_desc.get('content', '').strip()
            meta_description["content"] = desc_text
            meta_description["valid"] = True
            meta_description["length"] = len(desc_text)
            if len(desc_text) < 120:
                meta_description["warnings"].append("Meta description is too short (< 120 characters)")
            elif len(desc_text) > 320:
                meta_description["warnings"].append("Meta description is too long (> 160 characters)")
        else:
            meta_description["errors"].append("Meta description is missing")
    else:
        meta_title["errors"].append("Head tag is missing")
        meta_description["errors"].append("Head tag is missing")    
    return {
        "meta_title": meta_title,
        "meta_description": meta_description
    }

def get_heading_data(soup):
    headings = {"h1": [], "valid": True, "errors": [], "warnings": []}
    heading_count = {'h1_count': 0, 'h2_count': 0, 'h3_count': 0, 'h4_count': 0, 'h5_count': 0, 'h6_count': 0}
    for h1 in soup.find_all('h1'):
        headings["h1"].append(h1.get_text().strip())
        heading_count['h1_count'] += 1
    for i in range(2, 7):
        heading_count[f'h{i}_count'] = len(soup.find_all(f'h{i}'))
    if heading_count['h1_count'] == 0:
        headings["errors"].append("No H1 heading found")
        headings["valid"] = False
    elif heading_count['h1_count'] > 1:
        headings["warnings"].append(f"Multiple H1 headings found ({heading_count['h1_count']})")
    headings.update(heading_count)    
    return headings

def count_words(soup):
    body = soup.find('body')
    if body:
        text = body.get_text(strip=True)
        return str(len(text.split()))
    return "0"

def get_page_data(url, domain):
    url = normalize_url(url)
    internal_links = set()
    external_links = set()
    broken_links = set()
    images_data = {}
    head_data = {}
    headings_data = {}
    status_code = 'Error'
    links_in_page = set()
    word_count = "0"    
    try:
        print(f"Fetching data from: {url}")
        response = requests.get(url, timeout=8)
        status_code = response.status_code
        soup = BeautifulSoup(response.text, 'html.parser')        
        images_data = get_img_data(soup, domain)
        internal_links, external_links, broken_links, links_in_page = get_link_data(soup, domain, url)
        head_data = get_head_data(soup)
        headings_data = get_heading_data(soup)
        word_count = count_words(soup)        
        print(f"Found {len(internal_links)} internal links and {len(external_links)} external links")
        print(f"Found {images_data['total_images']} images, {images_data['images_without_alt']} without alt text")
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")    
    return [
        status_code, internal_links, external_links, broken_links, 
        images_data, head_data, headings_data, links_in_page, word_count
    ]

def format_links_data(links):
    result = {}
    for link_url, anchor_text, source_url in links:
        if link_url not in result:
            result[link_url] = []
        result[link_url].append(anchor_text)
    return result

def crawl_internal_links(start_url, max_links=100):
    start_url = normalize_url(start_url)
    print(f"Starting crawl from: {start_url}")
    domain = urllib.parse.urlparse(start_url).netloc
    status_code = 200
    try:
        response = requests.get(start_url, timeout=8)
        status_code = response.status_code
    except requests.RequestException as e:
        print(f"Request failed for start URL {start_url}: {e}")
        status_code = "Error"    
    visited_links = []
    links_to_visit = set()
    link_details = {}
    links_to_visit.add(start_url)
    all_external_links = set()
    all_broken_links = set()
    count = 0
    link_details[start_url] = ("[Start Page]", "")   
    while links_to_visit and count < max_links:
        current_link = links_to_visit.pop()
        current_link = normalize_url(current_link)
        if check_url(start_url, current_link):
            try:
                link_data = get_page_data(current_link, start_url)
                (page_status_code, internal_links, external_links, broken_links, 
                 images_data, head_data, headings_data, 
                 links_in_page, word_count) = link_data                
                default_link_info = ("[No Text]", "Unknown")
                link_info = link_details.get(current_link, default_link_info)
                formatted_external_links = format_links_data(external_links)
                formatted_internal_links = format_links_data(internal_links)
                formatted_broken_links = format_links_data(broken_links)                
                page_data = {
                    'page_url': current_link,
                    'meta_title': head_data.get('meta_title', {}),
                    'meta_description': head_data.get('meta_description', {}),
                    'headings': headings_data,
                    'external': formatted_external_links,
                    'internal': formatted_internal_links,
                    'broken': formatted_broken_links,
                    'word_count': word_count,
                    'images': images_data
                }
                visited_links.append(page_data)                
                for link_url, anchor_text, source_url in internal_links:
                    normalized_link_url = normalize_url(link_url)
                    if normalized_link_url not in link_details:
                        link_details[link_url] = (anchor_text, source_url)
                        links_to_visit.add(link_url)               
                all_external_links.update(external_links)
                all_broken_links.update(broken_links)
                count += 1
                time.sleep(2)
            except requests.RequestException as e:
                print(f"Request failed for {current_link}: {e}")
        else:
            print(f"Skipping external link: {current_link}")   
    print(f"Crawl completed.")
    return status_code, domain, start_url, visited_links

if __name__ == "__main__":
    start_url = str(input('Enter the URL to you want to scrape: '))
    start_url = normalize_url(start_url)
    try:
        status_code, domain, url, all_pages = crawl_internal_links(start_url, max_links=50)
        output_data = {
            "status": status_code,
            "domain": domain,
            "url": url,
            "pages": all_pages
        }        
        output_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site_data.json')
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            json.dump(output_data, output_file, indent=4)        
        print(f"Site data saved to: {output_file_path}")        
    except Exception as e:
        print(f"An error occurred during execution: {e}")