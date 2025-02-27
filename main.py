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
            full_url = urllib.parse.urljoin(domain, href)
            if urllib.parse.urlparse(full_url).netloc == urllib.parse.urlparse(domain).netloc:
                internal_links.add(full_url)
            else:
                external_links.add(full_url)
        print(f"Found {len(internal_links)} internal links and {len(external_links)} external links")
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")
    return internal_links, external_links

def crawl_internal_links(start_url, max_links=100):
    print(f"Starting crawl from: {start_url}")
    domain = urllib.parse.urlparse(start_url).scheme + "://" + urllib.parse.urlparse(start_url).netloc
    visited_links = []
    all_external_links = set()
    links_to_visit = set()
    initial_internal_links, initial_external_links = get_internal_links(start_url, domain)
    links_to_visit.update(initial_internal_links)
    all_external_links.update(initial_external_links)
    try:
        response = requests.get(start_url, timeout=10)
        visited_links.append({'link': start_url, 'status_code': response.status_code})
    except requests.RequestException as e:
        print(f"Request failed for start URL: {e}")
        visited_links.append({'link': start_url, 'status_code': 'Error'})
    
    count = 0
    while links_to_visit and count < max_links:
        try:
            current_link = links_to_visit.pop()
            print(f"Processing link {count+1}/{max_links}: {current_link}")
            
            if current_link not in {link_info['link'] for link_info in visited_links}:
                try:
                    response = requests.get(current_link, timeout=10)
                    status_code = response.status_code
                    visited_links.append({'link': current_link, 'status_code': status_code})
                    
                    new_internal_links, new_external_links = get_internal_links(current_link, domain)
                    links_to_visit.update(new_internal_links - {link_info['link'] for link_info in visited_links})
                    all_external_links.update(new_external_links)
                    time.sleep(2)
                except requests.RequestException as e:
                    print(f"Request failed for {current_link}: {e}")
                    visited_links.append({'link': current_link, 'status_code': 'Error'})            
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
                for link_info in internal_links:
                    status = link_info.get('status_code', 'Unknown')
                    file.write(f"Link: {link_info['link']}, Status Code: {status}\n")
        print(f"Internal links saved to: {internal_file_path}")
    except Exception as e:
        print(f"Error saving internal links: {e}")

    external_file_path = os.path.join(output_dir, 'external_links.txt')
    try:
        with open(external_file_path, 'w', encoding='utf-8') as file:
            if not external_links:
                file.write("No external links found.\n")
            else:
                for link in external_links:
                    file.write(f"Link: {link}\n")
        print(f"External links saved to: {external_file_path}")
    except Exception as e:
        print(f"Error saving external links: {e}")

if __name__ == "__main__":
    start_url = 'https://portyourdoc.com/'
    try:
        all_internal_links, all_external_links = crawl_internal_links(start_url, max_links=50)
        save_links_to_files(all_internal_links, all_external_links)
    except Exception as e:
        print(f"An error occurred during execution: {e}")
        save_links_to_files([], [])