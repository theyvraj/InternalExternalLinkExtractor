import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os

def get_internal_links(url, domain):
    internal_links = set()
    external_links = set()
    try:
        print(f"Fetching links from: {url}")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            
            anchor_text = link.get_text().strip() or "[No Text]"
            full_url = urllib.parse.urljoin(domain, href)
            if domain in full_url:
                internal_links.add((full_url, anchor_text, url))  
            else:
                external_links.add((full_url, anchor_text, url))  
        print(f"Found {len(internal_links)} internal links and {len(external_links)} external links")
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")
    return internal_links, external_links

def crawl_internal_links(start_url, max_links=100):
    print(f"Starting crawl from: {start_url}")
    domain = start_url
    visited_links = []
    all_external_links = set()
    links_to_visit = set()
    
    initial_internal_links, initial_external_links = get_internal_links(start_url, domain)
    links_to_visit.update({link[0] for link in initial_internal_links})
    all_external_links.update(initial_external_links)    
    link_details = {}
    for link_url, anchor_text, source_url in initial_internal_links:
        link_details[link_url] = (anchor_text, source_url)
    for link_url, anchor_text, source_url in initial_external_links:
        link_details[link_url] = (anchor_text, source_url)
    
    try:
        response = requests.get(start_url, timeout=10)
        visited_links.append({
            'link': start_url, 
            'status_code': response.status_code,
            'anchor_text': "Start URL",
            'source_url': "N/A"
        })
    except requests.RequestException as e:
        print(f"Request failed for start URL: {e}")
        visited_links.append({
            'link': start_url, 
            'status_code': 'Error',
            'anchor_text': "Start URL",
            'source_url': "N/A"
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
                    
                    visited_links.append({  
                        'link': current_link, 
                        'status_code': status_code,
                        'anchor_text': anchor_text,
                        'source_url': source_url
                    })
                    
                    new_internal_links, new_external_links = get_internal_links(current_link, domain)                    
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
                        'source_url': source_url
                    })
            
            count += 1
        except Exception as e:
            print(f"Error processing links: {e}")
            break
    
    print(f"Crawl completed. Visited {len(visited_links)} internal links and found {len(all_external_links)} external links.")
    return visited_links, all_external_links

def save_links_to_files(internal_links, external_links):
    output_dir = os.path.dirname(os.path.abspath(__file__))
    internal_file_path = os.path.join(output_dir, 'internal_links.txt')
    try:
        with open(internal_file_path, 'w', encoding='utf-8') as file:
            if not internal_links:
                file.write("No internal links found.\n")
            else:
                for i, link_info in enumerate(internal_links, 1):
                    file.write(f"Link {i}:\n")
                    file.write(f"  URL: {link_info['link']}\n")
                    file.write(f"  Status Code: {link_info['status_code']}\n")
                    file.write(f"  Anchor Text: {link_info['anchor_text']}\n")
                    file.write(f"  Found on: {link_info['source_url']}\n")
                    file.write("\n")
        print(f"Internal links saved to: {internal_file_path}")
    except Exception as e:
        print(f"Error saving internal links: {e}")
    external_file_path = os.path.join(output_dir, 'external_links.txt')
    try:
        with open(external_file_path, 'w', encoding='utf-8') as file:
            if not external_links:
                file.write("No external links found.\n")
            else:
                for i, link_tuple in enumerate(external_links, 1):
                    link_url, anchor_text, source_url = link_tuple
                    file.write(f"Link {i}:\n")
                    file.write(f"  URL: {link_url}\n")
                    file.write(f"  Anchor Text: {anchor_text}\n")
                    file.write(f"  Found on: {source_url}\n")
                    file.write("\n")
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