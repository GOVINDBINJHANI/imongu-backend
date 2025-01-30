from rest_framework import status
from rest_framework.response import Response
from payment.utils import *
from integrations.utils.google import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.views import APIView
from google.auth.exceptions import GoogleAuthError
import json
from rest_framework.permissions import AllowAny

class GoogleCalendar(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        # Check for authorization code
        auth_code = request.data.get("code")
        if not auth_code:
            return Response(
                {"error": "Authorization code not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            # Get the user
            user_id = GetUserId.get_user_id(request)
            user = User.objects.get(user_id=user_id)
            # Exchange code for token
            credentials = json.loads(exchange_code_for_token(auth_code))
            # Save credentials to the database
            GoogleToken.objects.update_or_create(
                user=user,
                defaults={
                    "access_token": credentials["token"],
                    "refresh_token": credentials["refresh_token"],
                    "token_uri": credentials["token_uri"],
                    "expiry": credentials["expiry"],
                },
            )

            return Response(
                {"message": "Google Calendar Authentication Successful"},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except GoogleAuthError as e:
            return Response(
                {"error": f"Google authentication failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):

        try:

            user_id = GetUserId.get_user_id(request)
            user_instance = User.objects.get(user_id=user_id)
            token = GoogleToken.objects.get(user_id=user_id)
            return Response(
                {
                    "message": "Google calender connected",
                    "email": user_instance.email,
                    "status": True,
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except GoogleToken.DoesNotExist:
            return Response(
                {"error": "User not authorized google calender"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request):

        try:

            user_id = GetUserId.get_user_id(request)
            user_instance = User.objects.get(user_id=user_id)
            token = GoogleToken.objects.get(user_id=user_id)
            revoke_google_token(user_id) 
            token.delete()
            return Response(
                {
                    "message": "Google calender disconnected successfully",
                    "email": user_instance.email,
                    "status": True,
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except GoogleToken.DoesNotExist:
            return Response(
                {"error": "User not authorized google calender"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuthorizeGoogleCalendar(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):

        try:
            # Get the user
            user_id = GetUserId.get_user_id(request)
            user = User.objects.get(user_id=user_id)
            authorization_url, state = get_auth_url()
            return Response({"authorization_url": authorization_url, "email" : user.email}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
