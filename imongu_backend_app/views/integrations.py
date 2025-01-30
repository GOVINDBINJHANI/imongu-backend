from urllib.parse import urlparse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from imongu_backend_app.Serializers import JiraConnectionSerializer
import json 
from imongu_backend_app.models import key_results,update_key_results
from imongu_backend_app.utils.jira import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger(__name__) 

class SaveJiraCredentials(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        try:
            user_id = GetUserId.get_user_id(request)
            company_id = request.data.get('company_id')

            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            feature_name = request.resolver_match.url_name
            activity_name = "Allow"
            role_id= validate_user_company_access(user_id, company_id)
            validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

            sub_domain_url = request.data.get('sub_domain_url', '')
            if not sub_domain_url.startswith('https://'):
                sub_domain_url = f'https://{sub_domain_url}.atlassian.net'
            result = urlparse(sub_domain_url)
            if not all([result.scheme, result.netloc]):
                return Response({"error": "Invalid URL provided"}, status=status.HTTP_400_BAD_REQUEST)
            request.data['sub_domain_url'] = sub_domain_url
            
            data = request.data
            data["user"] = user_id
            
            serializer = JiraConnectionSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'credential saved successfully'}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error" : str(e)} , status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': 'something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def put(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Allow"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        new_data = request.data
        jira_id = request.data.get('jira_id', '')
        if not jira_id:
            return Response({'error': 'missing mandatory fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            old_data = JiraConnection.objects.get(id=jira_id)
            serializer = JiraConnectionSerializer( old_data , data=new_data , partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response( serializer.data , status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except JiraConnection.DoesNotExist:
            return Response({'error': 'Credentials not found'}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Allow"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
        
        try:
            jira_creds = JiraConnection.objects.get(company_id=company_id)
            serializer = JiraConnectionSerializer(jira_creds)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except JiraConnection.DoesNotExist:
            return Response({"error" : "Jira Integration Not found"} , status=status.HTTP_404_NOT_FOUND)
        
    def delete(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Allow"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
        
        jira_id = request.query_params.get("jira_id")
        
        try:
            jira_creds = JiraConnection.objects.get(id=jira_id)
            jira_creds.delete()
            return Response({"message" : "Jira credentials removed successfully"}, status=status.HTTP_200_OK)
        except JiraConnection.DoesNotExist:
            return Response({"error" : "Jira Integration Not found"} , status=status.HTTP_404_NOT_FOUND)
        
class JiraWebhookView(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self,request):
        logger.info(f"Headers: {request.headers}")
        logger.info(f"Body: {request.body}")

        if not request.body:
            return Response({'error': 'Empty request body'}, status=status.HTTP_400_BAD_REQUEST)
        
        response = json.loads(request.body)
        issue = response.get('issue')
        issuetype = issue.get('fields').get('issuetype')
        sub_task = issuetype.get('subtask')
        issue_updated = response.get('issue_event_type_name')
        if sub_task and issue_updated == "issue_generic":
            key_id = issue.get('key')
            progress = issue.get('fields').get('status').get('name') 
            key_obj = key_results.objects.filter(subtask_key = key_id ).first()
            if key_obj:
                if progress == 'Done':
                    target_number = key_obj.target_number
                    key_obj.current_number = target_number
                    key_obj.overall_gain = 100
                elif progress == 'To Do':
                    key_obj.current_number = key_obj.initial_number
                    key_obj.overall_gain = 0
                elif progress == 'In Progress':
                    key_obj.current_number = key_obj.initial_number
                    key_obj.overall_gain = 50 
                key_obj.save()
                
        return Response({'message': response }, status=status.HTTP_200_OK)
    