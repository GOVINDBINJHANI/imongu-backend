import io
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from chatbot.utils.openai import generate_openai_response,generate_summary, query_llm
from chatbot.utils.retriveText import pdf_to_texts, format_response, format_response_of_query, extract_text_from_docx
import json
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
import logging
from rest_framework.views import APIView
import time

logger = logging.getLogger(__name__)


import json
import re



        

from django.http import StreamingHttpResponse

class ChatbotViews(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        start_time = time.time()  # Start timing
        logger.info("Received request: %s", request.data)

        try:
            # Extract user ID and company ID
            user_id = GetUserId.get_user_id(request)
            company_id = request.data.get('company_id')
            if not company_id:
                logger.error("Company ID is missing.")
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            feature_name = request.resolver_match.url_name
            activity_name = "Allow"
            role_id = validate_user_company_access(user_id, company_id)
            validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

            # Get goal_id and query from form-data
            goal_id = request.data.get('goal_id')
            query = request.data.get('query')
            logger.debug("Initial query: %s", query)

            # Get the access token from the Authorization header
            access_token = request.headers.get("Authorization")
            if not access_token:
                logger.error("Authorization header is missing.")
                return Response({"error": "Authorization header is required."}, status=status.HTTP_401_UNAUTHORIZED)

            # Handle file upload (optional)
            doc_file = request.FILES.get('file_upload')
            if doc_file:
                max_file_size = 2 * 1024 * 1024  # 2MB limit
                if doc_file.size > max_file_size:
                    logger.error("Uploaded file exceeds size limit.")
                    return Response({"error": "File size exceeds the limit (2MB)"}, status=status.HTTP_400_BAD_REQUEST)

                if doc_file.name.endswith('.pdf'):
                    doc_file_io = io.BytesIO(doc_file.read())
                    query = pdf_to_texts(doc_file_io)
                    logger.info("Extracted PDF text: %s", query)
                elif doc_file.name.endswith('.docx'):
                    query = extract_text_from_docx(doc_file)
                    logger.info("Extracted DOCX text: %s", query)

                # Generate response for document-based query and stream response
                openai_response = generate_openai_response(goal_id, query, access_token)
                json_response = json.loads(openai_response)
                formatted_response = format_response(json_response)
                return Response(formatted_response, status=status.HTTP_200_OK)


            if not query:
                logger.error("Query is None or empty.")
                return Response({"error": "Query cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

            # Get the access token from the Authorization header
            access_token = request.headers.get("Authorization")
            if not access_token:
                logger.error("Authorization header is missing.")
                return Response({"error": "Authorization header is required."}, status=status.HTTP_401_UNAUTHORIZED)

            # Check for summary-related keywords and generate a summary if present
            if 'summary' in query.lower() or 'summarize' in query.lower():
                logger.info(f"Generating summary for Goal ID: {goal_id} with Query: {query}")
                summary = generate_summary(goal_id, query, access_token)
                response = {"query": summary, "response_type": "query"}
                return Response(response, status=status.HTTP_200_OK)

            # Handling "help me to generate a new Goal" query
            if query.lower() == "help me to generate a new goal":
                logger.info(f"Generating a new goal for the query: {query}")
                # Here we override the response for the "help me to generate a new Goal"
                create_goal_response = {
                    "response_type": "create_goal",
                    "goal_data": {},
                    "message": "Goal creation initiated."
                }
                # Here, overriding the response type to 'create_goal'
                json_response = {"response_type": "response", "message": "Goal creation initiated."}
                json_response['response_type'] = "create_goal"  # Overriding response type
                formatted_response = format_response(json_response)
                elapsed_time = time.time() - start_time  # Calculate elapsed time
                logger.info(f"Time taken to generate response: {elapsed_time:.2f} seconds")
                return Response(formatted_response, status=status.HTTP_200_OK)

            # Handle LLM-related queries (query_llm)
            llm_response = query_llm(query)
            logger.info("LLM query response: %s", llm_response)

            # Override response_type for specific query
            try:
                json_response = json.loads(llm_response)
            except json.JSONDecodeError:
                json_response = {"response_type": "response", "message": llm_response}

            response_type = json_response.get('response_type', 'response')
            valid_response_types = ['create_goal', 'create goal', 'query', 'greet', 'response']

            if response_type in valid_response_types:
                if response_type in ['create_goal', 'create goal']:
                    formatted_response = format_response(json_response)
                    return Response(formatted_response, status=status.HTTP_200_OK)
                elif response_type == 'query':
                    formatted_response_of_query = format_response_of_query(json_response)
                    return Response(formatted_response_of_query, status=status.HTTP_200_OK)
                elif response_type in ['greet', 'response']:
                    return Response({
                        "query": query,
                        "response_type": response_type,
                        "message": json_response.get("message", "Response received from LLM.")
                    }, status=status.HTTP_200_OK)
                else:
                    logger.warning("Invalid response type in LLM response.")
                    return Response({"error": "Invalid response type"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "error": "Unhandled response type",
                "response": json_response
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("An unexpected error occurred.")
            # Handle "help me to generate a new Goal" case here in case of errors
            if query.lower() == "help me to generate a new goal":
                create_goal_response = {
                    "response_type": "create_goal",
                    "goal_data": {},
                    "message": "Goal creation initiated."
                }
                formatted_response = format_response(create_goal_response)
                return Response(formatted_response, status=status.HTTP_200_OK)
            else:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QueryLLMView(APIView):
    permission_classes = []  # No authentication required

    def post(self, request):
        logger.info("Received form data query: %s", request.data)

        try:
            # Extract query from the form-data (request.POST)
            query = request.data.get('query')  # This gets the 'query' field from form-data
            if not query:
                logger.error("Query is None or empty.")
                return Response({"error": "Query cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

            # Record the start time for the whole request
            start_time = time.time()

            # Call query_llm for generating the response
            llm_response = query_llm(query)

            # Calculate the time taken and log it
            elapsed_time = time.time() - start_time
            logger.info(f"LLM query response generated in {elapsed_time:.2f} seconds")

            logger.info("LLM query response: %s", llm_response)

            # Check if the response is JSON or text
            try:
                json_response = json.loads(llm_response)
            except json.JSONDecodeError:
                logger.warning("Response is not JSON, wrapping as JSON.")
                json_response = {"response_type": "response", "message": llm_response}

            # Format the response to match the desired structure
            response_data = {
                "query": query,
                "response_type": json_response.get("response_type", "response"),
                "message": json_response.get("message", llm_response)
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("An unexpected error occurred.")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
