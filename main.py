import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os
import json

def check_url(start_url, current_url):
    start_netloc = urllib.parse.urlparse(start_url).netloc
    current_netloc = urllib.parse.urlparse(current_url).netloc
    return start_netloc == current_netloc

def get_img_data(soup, domain):
    image_count = 0
    images_without_alt = set()   
    for img in soup.find_all('img'):
        image_count += 1
        if not img.get('alt') or img.get('alt').strip() == '':
            img_src = img.get('src', '')
            if img_src:
                full_img_src = urllib.parse.urljoin(domain, img_src)
                images_without_alt.add(full_img_src)
    return image_count, images_without_alt

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
        # Get meta title data
        title = head_tag.find('title')
        title_text = title.get_text() if title else "[No Title]"
        meta_data = {}
        for meta in head_tag.find_all('meta'):
            if meta.get('name'):
                meta_data[meta.get('name')] = meta.get('content')
            elif meta.get('property'):
                meta_data[meta.get('property')] = meta.get('content')            
        head_data = {
            'title': title_text,
            'meta_data': meta_data
        }
    return head_data
def get_heading_count(soup):
    heading_count = {'h1': 0, 'h2': 0, 'h3': 0, 'h4': 0, 'h5': 0, 'h6': 0}
    for i in range(1, 7):
        heading_count[f'h{i}'] = len(soup.find_all(f'h{i}'))        
    return heading_count
def get_page_data(url, domain):
    internal_links = set()
    external_links = set()
    image_count = 0
    images_without_alt = {}
    head_data = {"title": "[No Title]", "meta_data": {}}
    heading_count = {'h1': 0, 'h2': 0, 'h3': 0, 'h4': 0, 'h5': 0, 'h6': 0}
    status_code = 'Error'
    links_in_page = set()
    try:
        print(f"Fetching data from: {url}")
        response = requests.get(url, timeout=10)
        status_code = response.status_code
        soup = BeautifulSoup(response.text, 'html.parser')
        image_count, images_without_alt = get_img_data(soup, domain)
        internal_links, external_links, links_in_page = get_link_data(soup, domain, url)
        head_data = get_head_data(soup)
        heading_count = get_heading_count(soup)        
        print(f"Found {len(internal_links)} internal links and {len(external_links)} external links")        
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")    
    return [
        status_code, internal_links, external_links, image_count, images_without_alt, head_data, heading_count, links_in_page
        ]
def crawl_internal_links(start_url, max_links=100):
    print(f"Starting crawl from: {start_url}")
    visited_links = []
    links_to_visit = set()
    link_details = {}
    links_to_visit.add(start_url)
    all_external_links = set()
    count = 0
    link_details[start_url] = ("[Start Page]", "")    
    while links_to_visit and count < max_links:
        current_link = links_to_visit.pop()
        if check_url(start_url, current_link):
            try:
                link_data = get_page_data(current_link, start_url)
                status_code, internal_links, external_links, image_count, images_without_alt, head_data, heading_count, links_in_page = link_data
                default_link_info = ("[No Text]", "Unknown")
                link_info = link_details.get(current_link, default_link_info)                
                visited_links.append({
                    'link': current_link,
                    'status_code': status_code,
                    'anchor_text': link_info[0],
                    'source_url': link_info[1],
                    'internal_links_on_page' : list(links_in_page),
                    'image_count': image_count,
                    'images_without_alt': list(images_without_alt),
                    'head_data': head_data,
                    'heading_count': heading_count
                })                
                for link_url, anchor_text, source_url in internal_links:
                    if link_url not in link_details:
                        link_details[link_url] = (anchor_text, source_url)
                        links_to_visit.add(link_url)                
                all_external_links.update(external_links)
                count += 1
                time.sleep(2)
            except requests.RequestException as e:
                print(f"Request failed for {current_link}: {e}")
        else:
            print(f"Skipping external link: {current_link}")    
    print(f"Crawl completed.")
    return visited_links, all_external_links
def prepare_internal_links_dict(internal_links):
    internal_links_dict = {}
    for i, link_info in enumerate(internal_links, 1):
        internal_links_dict[f"link_{i}"] = {
            "url": link_info['link'],
            "status code": link_info['status_code'],
            "link text": link_info['anchor_text'],
            "links in this page": link_info['internal_links_on_page'],
            "found on": link_info['source_url'],
            "image count": link_info['image_count'],
            "images without alt": link_info['images_without_alt'],
            "head data": link_info['head_data'],
            "heading count": link_info['heading_count']
        }
    return internal_links_dict
def prepare_external_links_dict(external_links):
    unique_external_urls = {}
    for link_url, anchor_text, source_url in external_links:
        if link_url not in unique_external_urls:
            unique_external_urls[link_url] = (anchor_text, source_url)
    external_links_dict = {}
    for i, (link_url, (anchor_text, source_url)) in enumerate(unique_external_urls.items(), 1):
        external_links_dict[f"link_{i}"] = {
            "url": link_url,
            "link text": anchor_text,
            "found on": source_url
        }
    return external_links_dict
if __name__ == "__main__":
    start_url = str(input('Enter the URL to you want to scrap : '))
    try:
        all_internal_links, all_external_links = crawl_internal_links(start_url, max_links=50)
        internal_links_dict = prepare_internal_links_dict(all_internal_links)
        external_links_dict = prepare_external_links_dict(all_external_links)
        internal_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'internal_links.json')
        with open(internal_file_path, 'w', encoding='utf-8') as internal_file:
            json.dump(internal_links_dict, internal_file, indent=4)
        print(f"Internal links saved to: {internal_file_path}")
        external_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'external_links.json')
        with open(external_file_path, 'w', encoding='utf-8') as external_file:
            json.dump(external_links_dict, external_file, indent=4)
        print(f"External links saved to: {external_file_path}")
    except Exception as e:
        print(f"An error occurred during execution: {e}")