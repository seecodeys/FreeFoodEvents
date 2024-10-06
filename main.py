from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from functions import *
import pandas as pd
import time

# CalNet Credentials
user = ""
user_email = ""
user_password = ""

# Hugging Face Token
hf_token = ""

# OpenAI API Key
openai_api_key = ""

# Open events_database.csv and rejected_database.csv or reference
events_db_df = pd.read_csv("events_database.csv")
rejected_db_df = pd.read_csv("rejected_database.csv")
events_db_links_set = set(events_db_df.iloc[:,0])
rejected_db_links_set = set(rejected_db_df.iloc[:,0])
db_links_set = events_db_links_set | rejected_db_links_set
db_links_set = {item.strip("[]'\\n") for item in db_links_set}

# Initialize Selenium WebDriver
chrome_options = Options()
driver = webdriver.Chrome(options=chrome_options)

# Login to EdStem
edstem_login(driver, user, user_email, user_password)

# # Access threads_database.csv as list
# thread_dict_list = threads_database_parser()
#
# # Loop through all threads and adds links to new_post_links.txt
# for thread_dict in thread_dict_list:
#     dept_edstem_thread_scraper(driver, thread_dict)

# Scrape every single post from new_post_links.txt
with open('new_post_links.txt', 'r') as file:
    # Loop through each line (link) in the file
    for link in file:
        # Strip newline
        link = link.strip()
        # Check if link already exists in our database
        if link not in db_links_set:
            # Scrape post details as a dict
            post_dict = post_scraper(driver, link)

            # Evaluates post details and uses LLM to fill in fields
            post_llm_dict = post_llm(openai_api_key, post_dict)

            # Evaluates if post is an event and adds to respective database
            if post_llm_dict['is_event'] == "TRUE":
                # Add dictionary to events_database.csv
                with open("events_database.csv", mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames = post_llm_dict.keys())

                    # Add dict to database
                    writer.writerow(post_llm_dict)
                    print(f"Successfuly Added Event to events_database: {post_llm_dict['title']}")
            else:
                # Add dictionary to rejected_database.csv
                with open("rejected_database.csv", mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=post_llm_dict.keys())

                    # Add dict to database
                    writer.writerow(post_llm_dict)
                    print(f"Successfuly Added Post to rejected_database: {post_llm_dict['title']}")
        else:
            print(f"Currently Existing Link Skipped: {link}")

# Clear new_post_links.txt
with open('new_post_links.txt', 'w') as file:
    pass


