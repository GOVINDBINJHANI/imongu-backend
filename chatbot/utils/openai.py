from openai import OpenAI
from rest_framework.response import Response
from rest_framework import status
import yaml
from django.conf import settings
from chatbot.utils.goal import get_goal_data
from pinecone import Pinecone
import re
import os
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


client = OpenAI(api_key =settings.OPENAI_API_KEY)

# pc = Pinecone(api_key=settings.PINECONE_API_KEY)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index = pc.Index("imongu-app")


def load_prompt(name: str):
        with open("./chatbot/prompts/summary.yaml", 'r') as file:
            data = yaml.safe_load(file)
        
        for prompt in data.get("prompts", []):
            if prompt["name"] == name:
                return prompt["text"]
        return None  # Return None if prompt is not found       
                 

import time
import logging

logger = logging.getLogger(__name__)



def generate_summary(goal_id, query, access_token):
    logger.info(f"Starting summary generation for Goal ID: {goal_id}")
    
    # Start the timer
    start_time = time.time()
    
    try:
        # Fetch goal data
        logger.info("Fetching goal data...")
        json_string = get_goal_data(goal_id, access_token)
        
        if not json_string:
            logger.warning(f"No goal data found for Goal ID: {goal_id}")
            return "Goal data is not available."
        
        # Load and prepare the complete prompt
        complete_prompt = load_prompt(name="User Instruction For Summary")
        logger.info("Loading summary generation instructions completed.")

        # Validate the prompt
        if not complete_prompt:
            logger.error("The summary prompt could not be loaded.")
            return "Failed to load prompt for generating summary."
        
        full_prompt = f"User Instruction For generate Summary:\n\n{complete_prompt}"
        
        # Pre-log before OpenAI API call
        logger.info("Preparing OpenAI API request...")
        logger.debug(f"API Prompt: {full_prompt}")
        
        # OpenAI API call
        api_start_time = time.time()  # Timer for API-specific time
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=200,         
            temperature=0,            
            messages=[
                {"role": "system", "content": "You are designed to answer questions about a contract given by the user."},
                {"role": "assistant", "content": f"the contract is as follows: \n{json_string}"},
                {"role": "user", "content": full_prompt},
            ]
        )
        api_elapsed_time = time.time() - api_start_time
        logger.info(f"OpenAI API call completed in {api_elapsed_time:.2f} seconds.")
        
        # Extract the content
        summary = response.choices[0].message.content.strip()
        logger.info("Summary successfully generated.")

    except Exception as e:
        logger.exception(f"Error generating summary for Goal ID: {goal_id} - {str(e)}")
        summary = "An error occurred while generating the summary."

    # Calculate overall time taken
    total_elapsed_time = time.time() - start_time
    logger.info(f"Total time for summary generation (Goal ID: {goal_id}): {total_elapsed_time:.2f} seconds")
    
    return summary





def generate_openai_response(goal_id,query, access_token):
    #json_string = get_goal_data(goal_id)
    start_time = time.time()

    if goal_id:
        json_string = get_goal_data(goal_id, access_token)
    else:
        json_string = ''    
    context_system_prompt = load_prompt(name="context System Prompt")
    create_goal_prompt =load_prompt(name="User Instruction For Creating Goal")
    # summary_prompt = load_prompt(name="User Instruction For Summary")
    query_prompt = load_prompt(name="User Instruction For any query")

    complete_prompt = f"\n\n User instruction for creating goal : {create_goal_prompt} \n User instruction for any query related to my json data : {query_prompt}"
    
    response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    temperature = 0,
    max_tokens=300,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content":  f"you are a large language model trained by OpenAI, You are not allowed to respond with swear words, or offensive language.You are designed to answer questions about a contract given by the user in json. context of my json data : {context_system_prompt}"},
        {"role": "assistant", "content": f"The Actual json data : \n{json_string}"},
        {"role": "user", "content": f"You have to follow only one of user instruction at a time from these \n {complete_prompt}"},
        {"role": "user", "content": f"Do not forget to add response type in each response. And if query have create goal or generate goal then use create goal prompt only. \n User query : {query}"},
        
        ]
    )

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    logger.info(f"Time taken to generate Goal for Document: {elapsed_time:.2f} seconds")

    return response.choices[0].message.content


client = OpenAI()

def get_embedding(text, model="text-embedding-3-large"):
    """Get embedding for a given text."""
    start_time = time.time()  # Start timing
    text = text.replace("\n", " ")
    embedding = client.embeddings.create(input=[text], model=model).data[0].embedding
    elapsed_time = time.time() - start_time  # Calculate elapsed time
    logger.info(f"get_embedding took {elapsed_time:.2f} seconds")
    return embedding

def search_pinecone(query_embedding, top_k=15):
    """Search Pinecone with the query embedding."""
    start_time = time.time()  # Start timing
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace="how_to_guide")
    formatted_results = []
    
    if 'matches' not in results or not results['matches']:
        return "No matches found in Pinecone."

    for match in results['matches']:
        text = match['metadata'].get('text', ' ')
        text = re.sub(r'\n\s+', '', text)
        formatted_results.append(text)

    elapsed_time = time.time() - start_time  # Calculate elapsed time
    logger.info(f"search_pinecone took {elapsed_time:.2f} seconds")
    return "\n\n".join(formatted_results)



def query_llm(query):
    # Handle specific greetings directly
    if query.lower().strip() in ["hi", "hello", "hey"]:
        return "Hi, how can I assist you?"

    if query.lower().strip() in ["how are you", "how have you been", "how are you?", "how have you been?"]:
        return "I'm fine, thank you. How can I assist you?"

    # Measure time for embedding
    start_time = time.time()
    query_embedding = get_embedding(query)
    embedding_time = time.time() - start_time
    logger.info(f"get_embedding took {embedding_time:.2f} seconds")

    # Measure time for Pinecone search
    start_time = time.time()
    search_results = search_pinecone(query_embedding)
    search_time = time.time() - start_time
    logger.info(f"search_pinecone took {search_time:.2f} seconds")

    # Measure time for loading the prompt
    start_time = time.time()
    query_prompt = load_prompt(name="Query prompt")
    load_prompt_time = time.time() - start_time
    logger.info(f"load_prompt took {load_prompt_time:.2f} seconds")

    # Combine query, context, and instructions into one prompt
    prompt = (
        f"{query_prompt}\n\n"
        f"Input: {query}\n\n"
        f"Context:\n{search_results}\n\n"
        f"Please provide a concise response (under 50 words)."
    )

    logger.info("Search Result:\n{search_results}\n\n")

    # Measure time for LLM query with token limit and concise response
    start_time = time.time()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[ 
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,  
        temperature=0.7 ,
        # stream=True
    )
    llm_time = time.time() - start_time
    logger.info(f"LLM query took {llm_time:.2f} seconds")

    response_content = response.choices[0].message.content
    return response_content.strip()


import json

def safely_load_json(openai_response):
    """Attempts to parse the OpenAI response and fix common issues."""
    logger.debug(f"Received raw response: {openai_response}")

    try:
        # Try to directly parse the response
        return json.loads(openai_response)
    except json.JSONDecodeError as json_error:
        logger.error(f"Initial parsing failed with error: {json_error}")

        # Attempt to fix commonly truncated responses
        fix_attempted = False
        
        # We know the string is likely cut off at a description or sentence level.
        # Try to detect a problematic line and adjust.
        if "best" in openai_response:
            logger.info("Likely truncated at 'best', appending finishing string.")
            openai_response += '"}'  # Append possible missing part based on content structure
            fix_attempted = True
        
        # Check for more missing structure; append more if needed
        if openai_response.count('{') > openai_response.count('}'):
            openai_response += '}'
            fix_attempted = True

        # Try again to parse the fixed response
        try:
            if fix_attempted:
                logger.debug(f"Fixed response: {openai_response}")
            return json.loads(openai_response)
        except json.JSONDecodeError as second_error:
            logger.error(f"Parsing failed after attempt to fix: {second_error}")
            return None
