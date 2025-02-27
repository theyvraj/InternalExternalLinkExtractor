import requests
from bs4 import BeautifulSoup
import urllib.parse

def get_internal_links(url, domain):
    internal_links = set()
    external_links = set()
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            full_url = urllib.parse.urljoin(domain, href)
            if urllib.parse.urlparse(full_url).netloc == urllib.parse.urlparse(domain).netloc:
                internal_links.add(full_url)
            else:
                external_links.add(full_url)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    return internal_links, external_links

def crawl_internal_links(start_url):
    domain = urllib.parse.urlparse(start_url).scheme + "://" + urllib.parse.urlparse(start_url).netloc
    visited_links = []
    all_external_links = set()
    links_to_visit, external_links = get_internal_links(start_url, domain)
    all_external_links.update(external_links)
    
    while links_to_visit:
        current_link = links_to_visit.pop()
        if current_link not in {link_info['link'] for link_info in visited_links}:
            try:
                response = requests.get(current_link, timeout=5)
                status_code = response.status_code
                visited_links.append({'link': current_link, 'status_code': status_code})
                new_internal_links, new_external_links = get_internal_links(current_link, domain)
                links_to_visit.update(new_internal_links - {link_info['link'] for link_info in visited_links})
                all_external_links.update(new_external_links)
            except requests.RequestException as e:
                print(f"Request failed: {e}")
    return visited_links, all_external_links
start_url = 'https://portyourdoc.com/'
all_internal_links, all_external_links = crawl_internal_links(start_url)
with open('internal_links.txt', 'w', encoding='utf-8') as file:
    for link_info in all_internal_links:
        file.write(f"Link: {link_info['link']}, Status Code: {link_info['status_code']}\n")
with open('external_links.txt', 'w', encoding='utf-8') as file:
    for link in all_external_links:
        file.write(f"Link: {link}\n")