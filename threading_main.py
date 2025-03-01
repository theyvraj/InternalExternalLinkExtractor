import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os
import json
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    
    # Create a thread-safe collection for links
    link_queue = Queue()
    results = {
        "internal": set(),
        "external": set(),
        "broken": set(),
        "in_page": set()
    }
    
    # Add all links to the queue
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if '#' in href:
            continue            
        link_queue.put((href, link))
    
    # Worker function to process links
    def process_link():
        while not link_queue.empty():
            try:
                href, link = link_queue.get(block=False)
                anchor_text = link.get_text().strip() or "N/A"
                full_url = urllib.parse.urljoin(domain, href)
                full_url = normalize_url(full_url)
                
                try:
                    head_response = requests.head(full_url, timeout=5)
                    if head_response.status_code >= 400:
                        with threading.Lock():
                            results["broken"].add((full_url, anchor_text, url))
                except requests.RequestException:
                    with threading.Lock():
                        results["broken"].add((full_url, anchor_text, url))
                
                if domain in full_url:
                    with threading.Lock():
                        results["internal"].add((full_url, anchor_text, url))
                        results["in_page"].add(full_url)
                else:
                    with threading.Lock():
                        results["external"].add((full_url, anchor_text, url))
            except Exception as e:
                logger.error(f"Error processing link: {e}")
            finally:
                link_queue.task_done()
    
    # Use threads to process links in parallel
    threads = []
    for _ in range(min(10, link_queue.qsize())):  # Use up to 10 threads
        thread = threading.Thread(target=process_link)
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    return results["internal"], results["external"], results["broken"], results["in_page"]

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
        logger.info(f"Fetching data from: {url}")
        response = requests.get(url, timeout=8)
        status_code = response.status_code
        soup = BeautifulSoup(response.text, 'html.parser')        
        images_data = get_img_data(soup, domain)
        internal_links, external_links, broken_links, links_in_page = get_link_data(soup, domain, url)
        head_data = get_head_data(soup)
        headings_data = get_heading_data(soup)
        word_count = count_words(soup)        
        logger.info(f"[{url}] Found {len(internal_links)} internal links and {len(external_links)} external links")
        logger.info(f"[{url}] Found {images_data['total_images']} images, {images_data['images_without_alt']} without alt text")
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")    
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

def process_url(current_link, start_url, link_details, visited_pages_lock, visited_links, all_external_links, all_broken_links, links_to_visit, links_to_visit_lock):
    current_link = normalize_url(current_link)
    if not check_url(start_url, current_link):
        logger.info(f"Skipping external link: {current_link}")
        return
    
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
        
        with visited_pages_lock:
            visited_links.append(page_data)                
            
            # Add new internal links to the queue
            with links_to_visit_lock:
                for link_url, anchor_text, source_url in internal_links:
                    normalized_link_url = normalize_url(link_url)
                    
                    # Check if we've already visited this link or have it in our queue
                    already_visited = any(page['page_url'] == normalized_link_url for page in visited_links)
                    
                    if not already_visited and normalized_link_url not in link_details:
                        link_details[normalized_link_url] = (anchor_text, source_url)
                        links_to_visit.add(normalized_link_url)
                        
            # Update our collections of external and broken links
            all_external_links.update(external_links)
            all_broken_links.update(broken_links)
                
    except requests.RequestException as e:
        logger.error(f"Request failed for {current_link}: {e}")

def crawl_internal_links(start_url, max_links=100, max_threads=10):
    start_url = normalize_url(start_url)
    logger.info(f"Starting crawl from: {start_url}")
    domain = urllib.parse.urlparse(start_url).netloc
    status_code = 200
    
    try:
        response = requests.get(start_url, timeout=8)
        status_code = response.status_code
    except requests.RequestException as e:
        logger.error(f"Request failed for start URL {start_url}: {e}")
        status_code = "Error"    
    
    # Thread-safe collections
    visited_links = []  # List of visited pages and their data
    links_to_visit = set()  # Set of links to visit
    link_details = {}  # Dictionary of link details
    all_external_links = set()  # Set of all external links
    all_broken_links = set()  # Set of all broken links
    
    # Locks for shared resources
    visited_pages_lock = threading.Lock()
    links_to_visit_lock = threading.Lock()
    
    links_to_visit.add(start_url)
    link_details[start_url] = ("[Start Page]", "")
    
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        while links_to_visit and len(visited_links) < max_links:
            # Get the next batch of URLs to process
            with links_to_visit_lock:
                batch_size = min(max_threads, len(links_to_visit), max_links - len(visited_links))
                if batch_size <= 0:
                    break
                    
                current_batch = []
                for _ in range(batch_size):
                    if not links_to_visit:
                        break
                    current_link = links_to_visit.pop()
                    current_batch.append(current_link)
            
            # Process the batch in parallel
            futures = []
            for link in current_batch:
                future = executor.submit(
                    process_url, 
                    link, 
                    start_url, 
                    link_details, 
                    visited_pages_lock, 
                    visited_links, 
                    all_external_links, 
                    all_broken_links, 
                    links_to_visit, 
                    links_to_visit_lock
                )
                futures.append(future)
            
            # Wait for all URLs in this batch to be processed
            for future in futures:
                future.result()
                
            # Rate limiting
            time.sleep(0.5)  # Reduced from 2 seconds since we're processing in parallel
    
    logger.info(f"Crawl completed. Processed {len(visited_links)} pages.")
    return status_code, domain, start_url, visited_links

if __name__ == "__main__":
    start_url = str(input('Enter the URL to you want to scrape: '))
    start_url = normalize_url(start_url)
    
    # Optional parameters
    max_links = 50  # Maximum number of pages to crawl
    max_threads = 5  # Maximum number of concurrent threads
    
    try:
        status_code, domain, url, all_pages = crawl_internal_links(
            start_url, 
            max_links=max_links, 
            max_threads=max_threads
        )
        
        output_data = {
            "status": status_code,
            "domain": domain,
            "url": url,
            "pages": all_pages
        }        
        
        output_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site_data.json')
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            json.dump(output_data, output_file, indent=4)        
        
        logger.info(f"Site data saved to: {output_file_path}")        
    except Exception as e:
        logger.error(f"An error occurred during execution: {e}")