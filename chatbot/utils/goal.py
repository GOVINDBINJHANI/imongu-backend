import requests
from urllib.parse import urlencode
import logging
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

base_url = os.getenv("GOAL_URL_BASE")


def get_goal_data(goal_id, access_token):
    logger.info(f"Fetching goal data for Goal ID: {goal_id}")
    
    # Start timing
    start_time = time.time()

    # Ensure the base URL is loaded correctly
    if not base_url:
        logger.error("GOAL_URL_BASE is not set in the environment variables.")
        return {"error": "Base URL is missing in environment variables."}

    query_params = {"goal_id": goal_id}

    # Construct API URL
    api_url = base_url + '?' + urlencode(query_params)
    logger.info(f"Constructed API URL: {api_url}")
    
    # Adding headers with authorization and content type
    headers = {
        "Authorization": f"{access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Log the full headers
    logger.info(f"Request Headers: {headers}")

    # Make the request
    response = requests.get(api_url, headers=headers)
    
    # End timing and log elapsed time
    elapsed_time = time.time() - start_time
    logger.info(f"Time taken to fetch goal data for Goal ID {goal_id}: {elapsed_time:.2f} seconds")

    # Handle possible errors
    if response.status_code != 200:
        logger.error(f"Failed to fetch data. Status Code: {response.status_code}, Full Response: {response.text}")
        return {"error": "Failed to fetch data", "status_code": response.status_code}

    json_data = response.json()
    json_string = str(json_data)
    logger.info(f"Json Data for Goal id {goal_id} is {json_string}")
    return json_string
