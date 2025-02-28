import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os
import json
def get_internal_links(url, domain):
    internal_links = set()
    external_links = set()
    image_count = 0
    images_without_alt = []
    try:
        print(f"Fetching links from: {url}")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for img in soup.find_all('img'):
            image_count += 1
            if not img.get('alt') or img.get('alt').strip() == '':
                img_src = img.get('src', '')
                if img_src:
                    full_img_src = urllib.parse.urljoin(domain, img_src)
                    images_without_alt.append(full_img_src)
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if '#' in href:
                continue            
            anchor_text = link.get_text().strip() or "[No Text]"
            full_url = urllib.parse.urljoin(domain, href)
            if domain in full_url:
                internal_links.add((full_url, anchor_text, url))  
            else:
                external_links.add((full_url, anchor_text, url))  
        print(f"Found {len(internal_links)} internal links and {len(external_links)} external links")
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")
    return internal_links, external_links, image_count, images_without_alt
def get_page_title(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.get_text().strip() if title_tag else "[No Title]"
    except requests.RequestException as e:
        print(f"Failed to fetch title for {url}: {e}")
        return "[No Title]"
def get_head_data(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        head_tag = soup.find('head')
        if head_tag:            
            head_text = head_tag.get_text(separator='\n', strip=True)            
            meta_data = {}
            for meta in head_tag.find_all('meta'):
                if meta.get('name'):
                    meta_data[meta.get('name')] = meta.get('content')
                elif meta.get('property'):
                    meta_data[meta.get('property')] = meta.get('content')            
            return {
                'head_text': head_text,
                'meta_data': meta_data
            }
        return {"head_text": "[No Head Data]", "meta_data": {}}
    except requests.RequestException as e:
        print(f"Failed to fetch head data for {url}: {e}")
        return {"head_text": "[Error fetching head data]", "meta_data": {}}
def crawl_internal_links(start_url, max_links=100):
    print(f"Starting crawl from: {start_url}")
    domain = start_url
    visited_links = []
    all_external_links = set()
    links_to_visit = set()    
    initial_internal_links, initial_external_links, image_count, images_without_alt = get_internal_links(start_url, domain)
    links_to_visit.update({link[0] for link in initial_internal_links})
    all_external_links.update(initial_external_links)    
    link_details = {}
    for link_url, anchor_text, source_url in initial_internal_links:
        link_details[link_url] = (anchor_text, source_url)
    for link_url, anchor_text, source_url in initial_external_links:
        link_details[link_url] = (anchor_text, source_url)    
    try:
        response = requests.get(start_url, timeout=10)
        head_data = get_head_data(start_url)
        visited_links.append({
            'link': start_url, 
            'status_code': response.status_code,
            'anchor_text': "Start URL",
            'source_url': "N/A",
            'title': get_page_title(start_url),
            'image_count': image_count,
            'images_without_alt': images_without_alt,
            'head_data': head_data
        })
    except requests.RequestException as e:
        print(f"Request failed for start URL: {e}")
        visited_links.append({
            'link': start_url, 
            'status_code': 'Error',
            'anchor_text': "Start URL",
            'source_url': "N/A",
            'title': get_page_title(start_url),
            'image_count': 0,
            'images_without_alt': [],
            'head_data': {"head_text": "[Error fetching head data]", "meta_data": {}}
        })    
    count = 0
    while links_to_visit and count < max_links:
        try:
            current_link = links_to_visit.pop()
            print(f"Processing link {count+1}/{max_links}: {current_link}")          
            visited_urls = {link_info['link'] for link_info in visited_links}          
            if current_link not in visited_urls:
                try:
                    response = requests.get(current_link, timeout=10)
                    status_code = response.status_code                    
                    anchor_text, source_url = link_details.get(current_link, ("[No Text]", "Unknown")) 
                    new_internal_links, new_external_links, image_count, images_without_alt = get_internal_links(current_link, domain)
                    head_data = get_head_data(current_link)
                    visited_links.append({  
                        'link': current_link, 
                        'status_code': status_code,
                        'anchor_text': anchor_text,
                        'source_url': source_url,
                        'title': get_page_title(current_link),
                        'image_count': image_count,
                        'images_without_alt': images_without_alt,
                        'head_data': head_data
                    })                                        
                    for link_url, anchor_text, source_url in new_internal_links:
                        link_details[link_url] = (anchor_text, source_url)
                    for link_url, anchor_text, source_url in new_external_links:
                        link_details[link_url] = (anchor_text, source_url)                    
                    links_to_visit.update({link[0] for link in new_internal_links} - visited_urls)
                    all_external_links.update(new_external_links)                    
                    time.sleep(2)
                except requests.RequestException as e:
                    print(f"Request failed for {current_link}: {e}")
                    anchor_text, source_url = link_details.get(current_link, ("[No Text]", "Unknown"))                    
                    visited_links.append({
                        'link': current_link, 
                        'status_code': 'Error',
                        'anchor_text': anchor_text,
                        'source_url': source_url,
                        'title': "[No Title]",
                        'image_count': 0,
                        'images_without_alt': [],
                        'head_data': {"head_text": "[Error fetching head data]", "meta_data": {}}
                    })            
            count += 1
        except Exception as e:
            print(f"Error processing links: {e}")
            break    
    print(f"Crawl completed.")
    return visited_links, all_external_links
def save_links_to_files(internal_links, external_links):
    output_dir = os.path.dirname(os.path.abspath(__file__))
    internal_links_dict = {}
    for i, link_info in enumerate(internal_links, 1):
        internal_links_dict[f"link_{i}"] = {
            "url": link_info['link'],
            "status code": link_info['status_code'],
            "link text": link_info['anchor_text'],
            "found on": link_info['source_url'],
            "title": link_info['title'],
            "image count": link_info['image_count'],
            "images without alt": link_info['images_without_alt'],
            "head data": link_info['head_data']
        }
    internal_file_path = os.path.join(output_dir, 'internal_links.json')
    try:
        with open(internal_file_path, 'w', encoding='utf-8') as file:
            if not internal_links:
                json.dump({"message": "No internal links found."}, file, indent=4)
            else:
                json.dump(internal_links_dict, file, indent=4)
        print(f"Internal links saved to: {internal_file_path}")
    except Exception as e:
        print(f"Error saving internal links: {e}")
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
    external_file_path = os.path.join(output_dir, 'external_links.json')
    try:
        with open(external_file_path, 'w', encoding='utf-8') as file:
            if not unique_external_urls:
                json.dump({"message": "No external links found."}, file, indent=4)
            else:
                json.dump(external_links_dict, file, indent=4)
        print(f"External links saved to: {external_file_path}")
    except Exception as e:
        print(f"Error saving external links: {e}")
if __name__ == "__main__":
    start_url = str(input('Enter the URL to you want to scrap : '))
    try:
        all_internal_links, all_external_links = crawl_internal_links(start_url, max_links=50)
        save_links_to_files(all_internal_links, all_external_links)
    except Exception as e:
        print(f"An error occurred during execution: {e}")
        save_links_to_files([], [])