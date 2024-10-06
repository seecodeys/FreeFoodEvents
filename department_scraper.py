import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from functions import *

# List of UC Berkeley department URLs to search
# department_urls = department_scraper()
department_urls = ['https://econ.berkeley.edu/', 'https://www.stat.berkeley.edu/']  # For testing

# Set of visited URLs to avoid duplicates
visited_urls = set()

# File to save EdStem links
edstem_links_file = 'edstem_links.txt'

# Lock to prevent race conditions when writing to a file in parallel
from threading import Lock
file_lock = Lock()

def department_scraper():
    # The URL of the UC Berkeley Departments A-Z page
    url = "https://www.berkeley.edu/atoz/dept/"

    # Spoof a browser User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Send a GET request to the webpage with headers
    response = requests.get(url, headers=headers)

    # List to hold unique URLs
    url_list = []

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the page content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all <a> tags with href attributes
        a_tags = soup.find_all('a', href=True)

        # Extract the href attribute (URL) from each <a> tag, filter for .berkeley.edu/ and add to list if unique
        for tag in a_tags:
            link = tag['href']
            if link.endswith(".berkeley.edu/") and link not in url_list:
                url_list.append(link)

        # Save the URLs to a txt file
        with open('filtered_berkeley_links.txt', 'w') as file:
            for url in sorted(url_list):  # Sort the URLs for readability
                file.write(f"{url}\n")

        # Print the list for visual confirmation
        print("Filtered URLs as a list:")
        return url_list

    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")

    # Now `url_list` contains all the unique URLs that end with ".berkeley.edu/"

# Function to check if a URL is an HTML page (i.e., not a file like .pdf, .jpg, etc.)
def is_html_page(url):
    # Check common non-HTML file extensions
    non_html_extensions = ['.pdf', '.docx', '.jpg', '.png', '.gif', '.xlsx', '.pptx', '.zip']
    return not any(url.lower().endswith(ext) for ext in non_html_extensions)

# Function to scrape pages for EdStem links
def scrape_page(base_url, page_url):
    try:
        # Fetch the content of the page if it's an HTML page
        if not is_html_page(page_url):
            print(f"Skipping non-HTML file: {page_url}")
            return None

        response = requests.get(page_url)
        if response.status_code != 200:
            return None

        # Parse the page content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all <a> tags and check their href attributes
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Check if the href starts with the EdStem join URL
            if href.startswith("https://edstem.org/us/join/"):
                print(f"Found EdStem link: {href}")
                # Append only the EdStem link to the text file using a lock to prevent race conditions
                with file_lock:
                    with open(edstem_links_file, 'a') as file:
                        file.write(f"{href}\n")
                return True  # Stop processing further links for this department once an EdStem link is found

        # Extract internal links from the page and add to the crawl queue
        for link in links:
            href = link['href']
            # Convert relative URLs to absolute URLs
            full_url = urljoin(base_url, href)
            # Only consider internal links (same domain as base_url)
            if urlparse(base_url).netloc == urlparse(full_url).netloc:
                if full_url not in visited_urls and is_html_page(full_url):
                    visited_urls.add(full_url)
                    return full_url  # Return the next URL to crawl
    except Exception as e:
        print(f"Error scraping {page_url}: {e}")
        return None

# Function to crawl a department website, stop after finding one EdStem link
def crawl_department(base_url):
    queue = deque([base_url])  # Queue to hold pages to crawl
    visited_urls.add(base_url)

    while queue:
        current_url = queue.popleft()
        print(f"Crawling {current_url}")

        # Scrape the current page
        found_link = scrape_page(base_url, current_url)

        # Stop crawling further if an EdStem link is found
        if found_link is True:
            print(f"Moving on to the next department after finding EdStem link in {base_url}")
            return  # Stop further crawling for this department

        # If new URLs are found, add them to the queue
        elif found_link:
            queue.append(found_link)

# Main loop to go through each department in parallel
def main():
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(crawl_department, department_url) for department_url in department_urls]

        for future in as_completed(futures):
            try:
                future.result()  # Get result (to catch exceptions)
            except Exception as e:
                print(f"Error during processing: {e}")

if __name__ == "__main__":
    main()
