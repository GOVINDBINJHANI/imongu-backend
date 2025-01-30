from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..utils.outlook import *
from ..models import MicrosoftToken
from imongu_backend_app.models import User
from django.utils.timezone import now
from datetime import datetime, timedelta
from rest_framework.permissions import AllowAny
from imongu_backend.custom_permission.authorization import GetUserId
import logging
logger = logging.getLogger(__name__)

class MicrosoftCalendar(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            auth_code = request.data.get("code")
            user_id = GetUserId.get_user_id(request)
            if not auth_code:
                return Response(
                    {"error": "Code are required."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            token_response = exchange_microsoft_code_for_token(auth_code)
            MicrosoftToken.objects.update_or_create(
                user=user,
                defaults={
                    "access_token": token_response.get("access_token"),
                    "refresh_token": token_response.get("refresh_token"),
                    "expiry": now() + timedelta(seconds=token_response.get("expires_in", 0)),
                },
            )
            return Response(
                {"message": "Microsoft Calendar connected successfully."}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to connect Microsoft Calendar: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # def get(self, request):
    #     try:
    #         auth_url = get_microsoft_auth_url()
    #         return Response({"authorization_url": auth_url}, status=status.HTTP_200_OK)
    #     except Exception as e:
    #         return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def get(self, request):
        try:
            user_id = GetUserId.get_user_id(request)

            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            microsoft_token = MicrosoftToken.objects.filter(user=user).first()
            if not microsoft_token:
                return Response(
                    {"error": "Microsoft Calendar not connected.",
                     "status": False
                     },
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "message": "Microsoft Calendar connected",
                    "email": user.email,
                    "status": True,
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching Microsoft Calendar details: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve Microsoft Calendar details: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            user_id = GetUserId.get_user_id(request)

            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            microsoft_token = MicrosoftToken.objects.filter(user=user).first()
            if not microsoft_token:
                return Response(
                    {"error": "Microsoft Calendar not connected."},
                    status=status.HTTP_404_NOT_FOUND
                )

            microsoft_token.delete()

            return Response(
                {"message": "Microsoft Calendar disconnected successfully."},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            logger.error(f"Error disconnecting Microsoft Calendar: {str(e)}")
            return Response(
                {"error": f"Failed to disconnect Microsoft Calendar: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )