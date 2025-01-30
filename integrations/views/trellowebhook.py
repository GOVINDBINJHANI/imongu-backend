from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
# from integrations.models import TrelloConnection
from django.http import JsonResponse, HttpResponse
from integrations.Serializers import TrelloConnectionSerializer
from imongu_backend_app.utils.validate_user_access import validate_user_company_access
from integrations.utils.trello import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.permissions import AllowAny
from imongu_backend_app.models import User
import logging
import requests

logger = logging.getLogger(__name__)


class SaveTrelloCredentials(GenericAPIView):
    permission_classes = [AllowAny]  

    def post(self, request):
        try:
            user_id = GetUserId.get_user_id(request)
            company = request.data.get('company')
            connection_name = request.data.get('connection_name')

            if not company or not connection_name:
                return Response(
                    {'error': 'company_id and connection_name are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            feature_name = request.resolver_match.url_name
            activity_name = "Allow"

            # Validate user access
            role_id = validate_user_company_access(user_id, company)
            validate_feature_activity_access(role_id, company, feature_name, activity_name)

            # Validate and save Trello credentials
            serializer = TrelloConnectionSerializer(
                data=request.data, context={'request': request, 'user_id': user_id}
            )
            if serializer.is_valid():
                trello_connection = serializer.save()
                api_key = trello_connection.api_key
                token = trello_connection.token

                return Response(
                    {'message': 'Trello credentials saved successfully'},
                    status=status.HTTP_201_CREATED
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except ValueError as ve:
            logger.error(f"Value error: {ve}")
            return Response(
                {'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as pe:
            logger.error(f"Permission denied: {pe}")
            return Response(
                {'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        try:
            user_id = GetUserId.get_user_id(request)
            company = request.query_params.get('company_id')

            if not company:
                return Response(
                    {'error': 'company_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            trello_connection = TrelloConnection.objects.filter(user_id=user_id, company_id=company).first()

            if not trello_connection:
                return Response(
                    {
                        'error': 'No Trello connection found for the given user and company',
                        'message': 'Trello is not connected',
                        'status': False
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = TrelloConnectionSerializer(trello_connection)
            response_data = {
                'message': 'Trello is connected',
                'status': True,
                'data': serializer.data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as ve:
            logger.error(f"Value error: {ve}")
            return Response(
                {'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as pe:
            logger.error(f"Permission denied: {pe}")
            return Response(
                {'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def put(self, request):
        try:
            user_id = GetUserId.get_user_id(request)
            company = request.data.get('company')
            connection_name = request.data.get('connection_name')

            if not company or not connection_name:
                return Response(
                    {'error': 'company_id and connection_name are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            validate_user_company_access(user_id, company)
            trello_connection = TrelloConnection.objects.filter(user_id=user_id, company_id=company).first()

            if not trello_connection:
                return Response(
                    {'error': 'Trello connection not found for this user and company'},
                    status=status.HTTP_404_NOT_FOUND
                )

            trello_connection.connection_name = connection_name
            trello_connection.api_key = request.data.get('api_key', trello_connection.api_key)
            trello_connection.token = request.data.get('token', trello_connection.token)
            trello_connection.save()

            return Response(
                {'message': 'Trello credentials updated successfully'},
                status=status.HTTP_200_OK
            )

        except ValueError as ve:
            logger.error(f"Value error: {ve}")
            return Response(
                {'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as pe:
            logger.error(f"Permission denied: {pe}")
            return Response(
                {'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            user_id = GetUserId.get_user_id(request)
            company = request.query_params.get('company_id')

            if not company:
                return Response({'error': 'company_id is required'}, status=status.HTTP_400_BAD_REQUEST)

            validate_user_company_access(user_id, company)
            trello_connection = TrelloConnection.objects.filter(user_id=user_id, company_id=company).first()

            if not trello_connection:
                return Response(
                    {'error': 'Trello connection not found for this user and company'},
                    status=status.HTTP_404_NOT_FOUND
                )

            trello_connection.delete()

            return Response(
                {'message': 'Trello connection deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )

        except ValueError as ve:
            logger.error(f"Value error: {ve}")
            return Response(
                {'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as pe:
            logger.error(f"Permission denied: {pe}")
            return Response(
                {'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TrelloWebhookView(GenericAPIView):
    permission_classes = [AllowAny]

    def head(self, request, *args, **kwargs):
        return HttpResponse(status=200)

    def post(self, request, *args, **kwargs):
        try:
            payload = request.data
            action_type = payload.get("action", {}).get("type")
            card_id = payload.get("action", {}).get("data", {}).get("card", {}).get("id")
            list_after = payload.get("action", {}).get("data", {}).get("listAfter", {}).get("name")  # New list name
            list_before = payload.get("action", {}).get("data", {}).get("listBefore", {}).get("name")  # Old list name

            if not action_type or not card_id:
                logger.warning("Incomplete payload received from Trello")
                return Response(
                    {'error': 'Incomplete payload received'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Handle checklist item completion
            if action_type == 'updateCheckItemStateOnCard':
                checklist_item_id = payload.get("action", {}).get("data", {}).get("checkItem", {}).get("id")
                checklist_item_state = payload.get("action", {}).get("data", {}).get("checkItem", {}).get("state")

                if checklist_item_id and checklist_item_state:
                    try:
                        update_key_result_and_related_tables(card_id, checklist_item_id, checklist_item_state)
                    except Exception as e:
                        logger.error(f"Failed to update key result: {e}")
                        return Response(
                            {'error': 'Failed to update key result'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

            # Handle card movements between lists
            elif action_type == 'updateCard' and list_after and list_before:
                try:
                    update_okr_progress_on_card_movement(card_id, list_after)
                except Exception as e:
                    logger.error(f"Failed to update OKR progress: {e}")
                    return Response(
                        {'error': 'Failed to update OKR progress'}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            return Response({"status": "processed"}, status=status.HTTP_200_OK)

        except KeyError as ke:
            logger.error(f"Missing key in the payload: {ke}")
            return Response(
                {'error': f"Missing key: {ke}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"An unexpected error occurred while processing the Trello webhook: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    