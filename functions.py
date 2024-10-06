from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from gradio_client import Client, handle_file
from datetime import datetime
from openai import OpenAI
import pandas as pd
import re
import time
import csv

# Authenticates and logs into EdStem using CalNet for the session
def edstem_login(driver, user, user_email, user_password):
    # Navigate to EdStem login page
    edstem_login_url = "https://edstem.org/us/login"
    driver.get(edstem_login_url)

    # Wait for the page to load and URL to be updated
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "x1")))

    # Get current URL
    current_url = driver.current_url

    # Execute EdStem authentication
    if "edstem.org/us/login" in current_url:
        print("Autofilling user EdStem email...")

        # Wait for the login email box to appear
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "x1")))
        email_field = driver.find_element(By.ID, "x1")

        # Fill email and submit
        email_field.send_keys(user_email)
        edstem_submit_button = driver.find_element(By.CLASS_NAME, "start-btn")
        edstem_submit_button.click()

        # Wait to see if CalNet authentication needed
        try:
            # Wait for the CalNet ID box to appear
            WebDriverWait(driver, 10).until(EC.url_contains("auth.berkeley.edu"))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))

            # Execute CalNet authentication
            print("Autofilling user CalNet details...")

            # Select user and password field boxes
            user_field = driver.find_element(By.ID, "username")
            password_field = driver.find_element(By.ID, "password")

            # Fill CalNet ID, password and submit
            user_field.send_keys(user)
            password_field.send_keys(user_password)
            calnet_submit_button = driver.find_element(By.ID, "submit")
            calnet_submit_button.click()

            # Wait for Duo Push authentication
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "app")))
            WebDriverWait(driver, 120).until(EC.presence_of_element_located((By.CLASS_NAME, "dash-courses")))

            print("Authentication Completed!")
        except Exception as e:
            pass

# Scrapes each department's EdStem event thread and adds post links to new_post_links.txt
def dept_edstem_thread_scraper(driver, thread_dict):
    # Assign dictionary values to variables
    dept_name = thread_dict['Department Name']
    thread_name = thread_dict['Thread Name']
    thread_link = thread_dict['Thread Link']

    # File to save new post links
    new_post_links_file = 'new_post_links.txt'

    # Navigate to department events thread
    driver.get(thread_link)

    # Wait until the specific container element is present on the page
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "dlr-list")))

    # Get the scrolling container element
    scroll_container = driver.find_element(By.CLASS_NAME, "dlr-list")

    # Scroll to the bottom of the threads container
    print("Loading all posts...")
    last_scroll_height = 0  # Variable to keep track of the previous scroll height

    while True:
        # Get the current scroll height of the container
        current_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)

        # Scroll down the specific container by executing JavaScript
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)

        # Wait for the new content to load (adjust this time based on page speed)
        time.sleep(2)

        # Check if the scroll height has changed
        if current_scroll_height == last_scroll_height:
            print(f"All posts from the {dept_name} department's {thread_name} thread have been loaded!")
            break  # Exit the loop if scrolling does not change the scroll height

        last_scroll_height = current_scroll_height  # Update the scroll height for the next iteration

    # Find all threads with the <a> tag and class "dtl-thread discuss-feed-thread dft-full"
    event_divs = driver.find_elements(By.CLASS_NAME, "dlv-item")

    # Iterate through each thread and add link to events_list
    print("Adding post links to database...")
    for index, event_div in enumerate(event_divs):
        # Extract the link from thread
        href = event_div.find_element(By.TAG_NAME, "a").get_attribute("href")
        # Add link to new_post_links_file
        with open(new_post_links_file, 'a') as file:
            file.write(f"{href}\n")
    print(f"Finished adding all post links from the {dept_name} department's {thread_name} thread to database!")

# Opens threads_database.csv and converts it into a list of dictionaries
def threads_database_parser():
    # Path to threads_database.csv
    threads_database_file_path = 'threads_database.csv'

    # Open and read the database
    print("Opening Threads Database...")
    with open(threads_database_file_path, mode='r', newline='', encoding='utf-8') as file:
        # Use csv.DictReader to read the CSV as a list of dictionaries
        reader = csv.DictReader(file)

        # Convert to a list of dictionaries
        data_list = list(reader)

        print("Threads Database parsed!")
        return data_list

# Runs MiniCPM-Llama3-V-2_5 LLM to analyze post and associated poster to fill in event details
def post_image_llm(hf_token, post_text, image_url):
    # Define dictionary to be filled
    post_llm_dict = {
        "is_event": None,
        "event_type": None,
        "event_date": None,
        "event_time": None,
        "event_location": None,
        "is_food": None,
        "food_type": None
    }

    # If no image, use black image
    if image_url == None:
        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/A_black_image.jpg/640px-A_black_image.jpg"

    # Initialize the client for the openbmb/MiniCPM-Llama3-V-2_5 model
    client = Client("openbmb/MiniCPM-Llama3-V-2_5", hf_token=hf_token)

    # Additional context (from post_text) and define questions asked
    question = f"""
    Additional Context:
    {post_text}

    Questions to Answer:
    is_event = TRUE/FALSE
    event_type = Meeting/Workshop/Seminar/Lecture/Social/Fair
    event_date = <FORMAT DATE IN %d-%b-%Y FORMAT, IF YEAR IS NOT GIVEN USE YEAR GIVEN DATE POSTED>
    event_time = <FORMAT TIME IN XX:XX AM/PM FORMAT>
    event_location = <FILL IN LOCATION>
    is_food = TRUE/FALSE/LIKELY (TRUE IF MENTIONED, FALSE IF NOT MENTIONED AND NOT HOSTED BY BIG COMPANY, LIKELY IF NOT MENTIONED BUT HOSTED BY BIG COMPANY, PUT LIKELY)
    food_type = None/Not Specified/<ONE WORD ANSWER OF WHAT THE FOOD WILL BE>
    """

    # Upload the image
    upload_result = client.predict(
        image=handle_file(image_url),  # Handle the image from the URL
        _chatbot=[],  # Empty chatbot context
        api_name="/upload_img"  # Use the correct API endpoint for image analysis
    )

    # Send the question to the model using the `/respond` endpoint
    question_result = client.predict(
        _chat_bot=[[question, None]],  # Send the question with chatbot context
        params_form="Sampling",  # Use sampling for the generation
        num_beams=3,  # Number of beams for beam search (for better responses)
        repetition_penalty=1.2,  # Avoid repetitive outputs
        repetition_penalty_2=1.05,
        top_p=0.8,
        top_k=100,
        temperature=0.7,  # Adjust creativity level
        api_name="/respond"  # This is the endpoint for generating responses
    )

    # Output the final result
    question_response = question_result[0][1]

    # Regular expression to extract variables and their values
    regex = fr".*?([A-Za-z0-9_]+).*?[=:](.*)"

    # Find all matches in the text
    matches = re.findall(regex, question_response)

    # Loop through each match and assign them to original variables
    for match in matches:
        if match[0] in post_llm_dict:
            try:
                post_llm_dict[match[0]] = match[1].strip()
            except:
                pass

    print(question_response)
    print(post_llm_dict)
    return post_llm_dict

# Scrapes post and stores in database
def post_scraper(driver, post_link):
    # Open post
    driver.get(post_link)

    # Wait for the page to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "discuss-thread-base")))

    # Initialize dictionary
    post_dict = {
        "post_link": [post_link],
        "title": [None],
        "date_posted": [None],
        "posted_by": [None],
        "description": [None],
        "image_url": [None]
    }

    # Try to assign each event detail with its own try-except block

    # Title
    try:
        post_dict['title'][0] = driver.find_element(By.CLASS_NAME, "disthrb-title").text
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    # Date Posted
    try:
        post_dict['date_posted'][0] = datetime.strptime(driver.find_element(By.CLASS_NAME, "disthrb-date").find_element(By.TAG_NAME, "time").get_attribute("datetime"), "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d-%b-%Y %H:%M:%S.%fZ")
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    # Posted By
    try:
        post_dict['posted_by'][0] = driver.find_element(By.CLASS_NAME, "disthrb-user-name").text
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    # Description
    try:
        post_dict['description'][0] = driver.find_element(By.CLASS_NAME, "amber-display-document").text
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    # Image URL
    try:
        post_dict['image_url'][0] = driver.find_element(By.CLASS_NAME, "imgl-inner").find_element(By.TAG_NAME, "img").get_attribute("src")
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    # Save to Pandas dataframe
    df = pd.DataFrame(post_dict)

    # Return post_dict
    print(f"New Post Scraped: {post_dict['title'][0]}")
    return post_dict


# Runs gpt-4o-mini LLM to analyze post to fill in event details
def post_llm(openai_api_key, post_dict):
    # Define dictionary to be filled
    post_llm_dict = {
        "is_event": None,
        "event_type": None,
        "event_date": None,
        "event_time": None,
        "event_location": None,
        "is_food": None,
        "food_type": None
    }

    # Initiate Client
    client = OpenAI(
        # This is the default and can be omitted
        api_key=openai_api_key
    )

    # Define query
    query = f"""
        Context:
        {post_dict}

        Questions to Answer:
        is_event = TRUE/FALSE
        event_type = Meeting/Workshop/Seminar/Lecture/Social/Fair
        event_date = <FORMAT DATE IN %d-%b-%Y FORMAT, IF YEAR IS NOT GIVEN USE YEAR GIVEN DATE POSTED>
        event_time = <FORMAT TIME IN XX:XX AM/PM FORMAT>
        event_location = <FILL IN LOCATION>
        is_food = TRUE/FALSE/LIKELY (TRUE IF MENTIONED, FALSE IF NOT MENTIONED AND NOT HOSTED BY BIG COMPANY, LIKELY IF NOT MENTIONED BUT HOSTED BY BIG COMPANY, PUT LIKELY)
        food_type = None/Not Specified/<ONE WORD ANSWER OF WHAT THE FOOD WILL BE>
    """

    try:
        # Create the chat completion request
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": query
                }
            ]
        )

        # Output the final result
        question_response = response.choices[0].message.content

        # Regular expression to extract variables and their values
        regex = fr".*?([A-Za-z0-9_]+).*?[=:](.*)"

        # Find all matches in the text
        matches = re.findall(regex, question_response)

        # Loop through each match and assign them to original variables
        for match in matches:
            if match[0] in post_llm_dict:
                try:
                    post_llm_dict[match[0]] = match[1].strip()
                except:
                    pass

        # Update post_dict with new details
        post_dict.update(post_llm_dict)

        print("New Post Analyzed: ", post_dict['title'][0])
        return post_dict

    except Exception as e:
        pass