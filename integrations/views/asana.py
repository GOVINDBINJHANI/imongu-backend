from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
from integrations.models import AsanaConnection
from integrations.utils.asana_utils import *
from imongu_backend.custom_permission.authorization import GetUserId
from django.http import JsonResponse
from imongu_backend_app.models import User
from rest_framework.response import Response
from django.http import HttpResponse
import logging
logger = logging.getLogger(__name__)

class AsanaConnectionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            user_id = GetUserId.get_user_id(request)
            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"error": "User not found"}, status=404)

            company_id = request.data.get('company_id')
            connection_name = request.data.get('connection_name')
            access_token = request.data.get('access_token')

            if not company_id or not access_token:
                return JsonResponse(
                    {"error": "company_id and access_token are required"},
                    status=400
                )

            connection = AsanaConnection.objects.create(
                user=user,
                company_id=company_id,
                connection_name=connection_name,
                access_token=access_token,
            )

            return JsonResponse({"message": "Asana connection created successfully"},status=201)

        except KeyError as e:
            return JsonResponse({"error": f"Missing key in request data: {str(e)}"}, status=400)

        except Exception as e:
            logger.error(f"Unexpected error in AsanaConnectionView for user_id {user_id}: {e}")
            return JsonResponse({"error": "An unexpected error occurred. Please try again later."}, status=500)
        

    def get(self, request, *args, **kwargs):
        try:
            user_id = GetUserId.get_user_id(request)
            company_id = request.query_params.get('company_id')

            if not company_id:
                return JsonResponse({"error": "company_id is required"}, status=400)

            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"error": "User not found"}, status=404)

            try:
                connection = AsanaConnection.objects.get(user=user, company_id=company_id)
                return JsonResponse({
                    "message": "Asana is connected",
                    "status": True,
                    "connection_name": connection.connection_name,
                    "access_token": connection.access_token,
                    "company_id": connection.company_id
                })
            except AsanaConnection.DoesNotExist:
                return JsonResponse({
                    "message": "Asana is not connected",
                    "status": False,
                    "error": "Asana connection not found"
                }, status=404)

        except Exception as e:
            logger.error(f"Unexpected error in AsanaConnectionView for user_id {user_id}: {e}")
            return JsonResponse({"error": "An unexpected error occurred. Please try again later."}, status=500)

    def put(self, request, *args, **kwargs):
        try:
            user_id = GetUserId.get_user_id(request)
            company_id = request.data.get('company_id')
            connection_name = request.data.get('connection_name')
            access_token = request.data.get('access_token')

            if not company_id:
                return JsonResponse({"error": "company_id is required"}, status=400)

            try:
                user = User.objects.get(user_id=user_id)
                connection = AsanaConnection.objects.get(user=user, company_id=company_id)

                if connection_name:
                    connection.connection_name = connection_name
                if access_token:
                    connection.access_token = access_token

                connection.save()
                return JsonResponse({"message": "Asana connection updated successfully"}, status=200)

            except User.DoesNotExist:
                return JsonResponse({"error": "User not found"}, status=404)
            except AsanaConnection.DoesNotExist:
                return JsonResponse({"error": "Asana connection not found"}, status=404)

        except Exception as e:
            logger.error(f"Unexpected error in AsanaConnectionView for user_id {user_id}: {e}")
            return JsonResponse({"error": "An unexpected error occurred. Please try again later."}, status=500)

    def delete(self, request, *args, **kwargs):
        try:
            user_id = GetUserId.get_user_id(request)
            company_id = request.query_params.get('company_id')

            if not company_id:
                return JsonResponse({"error": "company_id is required"}, status=400)

            try:
                user = User.objects.get(user_id=user_id)
                connection = AsanaConnection.objects.get(user=user, company_id=company_id)
                connection.delete()
                return JsonResponse({"message": "Asana connection deleted successfully"}, status=200)

            except User.DoesNotExist:
                return JsonResponse({"error": "User not found"}, status=404)
            except AsanaConnection.DoesNotExist:
                return JsonResponse({"error": "Asana connection not found"}, status=404)
        except Exception as e:
            logger.error(f"Unexpected error in AsanaConnectionView for user_id {user_id}: {e}")
            return JsonResponse({"error": "An unexpected error occurred. Please try again later."}, status=500)

class AsanaWebhookView(APIView):
    permission_classes = [AllowAny]

    def head(self, request, *args, **kwargs):
        return HttpResponse(status=200)

    def post(self, request, *args, **kwargs):
        try:
            x_hook_secret = request.headers.get("X-Hook-Secret")
            if x_hook_secret:
                response = HttpResponse(status=200)
                response["X-Hook-Secret"] = x_hook_secret
                return response

            payload = request.data
            events = payload.get("events", [])
            logger.info(f"Received POST webhook data: {events}")

            for event in events:
                action_type = event.get("action")
                resource = event.get("resource", {})
                resource_type = resource.get("resource_type")
                task_id = resource.get("gid")
                parent = event.get("parent", {})
                change = event.get("change", {})
                field_changed = change.get("field")
                resource_subtype = resource.get("resource_subtype")
                value_changed = change.get("value")

                if resource_type == "task":
                    if field_changed == "completed" and action_type == "changed":
                        update_key_result_on_subtask_completion(task_id, resource_subtype)

                elif resource_type == "story" and resource_subtype in ["marked_incomplete", "marked_complete"]: 
                    parent_task_id = parent.get("gid")
                    if parent_task_id:
                        update_key_result_on_subtask_completion(parent_task_id, resource_subtype)

                elif resource_type == "task" and parent is not None and parent.get("resource_type") == "section":
                    section_gid = parent.get("gid")

                    if action_type == "added":
                        section_name = get_section_name(section_gid)
                        if "to do" in section_name.lower():
                            update_okr_progress_on_task_status_change(task_id, "To Do")
                        elif "doing" in section_name.lower():
                            update_okr_progress_on_task_status_change(task_id, "Doing")
                        elif "done" in section_name.lower():
                            update_okr_progress_on_task_status_change(task_id, "Done")


            return Response({"status": "processed"}, status=200)

        except KeyError as ke:
            logger.error(f"Missing key in the payload: {ke}")
            return Response({"error": f"Missing key: {ke}"}, status=400)
        except Exception as e:
            logger.exception(f"Unexpected error in Asana webhook: {e}")
            return Response({"error": "An unexpected error occurred"}, status=500)
