from PyPDF2 import PdfReader
from docx import Document
from datetime import datetime, timedelta
import random


def pdf_to_texts(file_data):
    pages = ""
    reader = PdfReader(file_data)
    for page in reader.pages:
        pages += page.extract_text()
    return pages


def extract_text_from_docx(docx_file_path):
    doc = Document(docx_file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text


def format_response(json_response):
    # Extract values dynamically with fallbacks if missing
    session = json_response.get("session", "0")
    
    # Use dynamic data, fallback only if missing
    title = json_response.get("title", "Goal Title Placeholder")
    description = json_response.get("description", "Goal Description Placeholder")
    
    # Objective data
    objective_title = json_response.get("objective_title", "Objective Title Placeholder")
    objective_description = json_response.get("objective_description", "Objective Description Placeholder")
    
    # Key result data
    key_result_title = json_response.get("key_result_title", "Key Result Title Placeholder")
    key_result_description = json_response.get("key_result_description", "Key Result Description Placeholder")
    
    # Dynamically assign deadline from the response, or fallback
    deadline = json_response.get(
        "deadline",
        (datetime.now().date() + timedelta(days=random.randint(20, 50))).strftime("%Y-%m-%d")
    )

    # Construct the hierarchical structure dynamically
    response = {
        "session": session,
        "title": title,
        "description": description,
        "parent": False,
        "child_type": "goal",
        "overall_gain": "",
        "children": [
            {
                "objective_title": objective_title,
                "objective_description": objective_description,
                "child_type": "objective",
                "overall_gain": "",
                "children": [
                    {
                        "key_result_title": key_result_title,
                        "key_result_description": key_result_description,
                        "child_type": "key_result",
                        "overall_gain": "",
                        "key_result_type": "Should increase to",
                        "unit": "Number",
                        "initial_number": 0,
                        "target_number": 100,
                        "deadline": deadline
                    }
                ]
            }
        ],
        "response_type": json_response.get("response_type", "create_goal"),
    }
    return response


def format_response_of_query(json_response):
    query = json_response.get("query", None)
    if query in ["None", "none", "null", "Null"] or not query:
        query = "Please speficify your query in details."
    response = {"query": query, "response_type": "query"}
    return response
