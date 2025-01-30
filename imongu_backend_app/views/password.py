from django.contrib.auth.hashers import make_password
from rest_framework import status
from imongu_backend_app.models import User
from imongu_backend_app.Serializers import userserializers
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.conf import settings
import jwt, datetime
from urllib.parse import urlencode
from imongu_backend_app.utils.email import send_forget_ps_email
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.permissions import AllowAny


class Forgotpassword_mail(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.filter(email=email).first()
        except User.DoesNotExist:
            return Response(
                {"error": "email is not registered"}, status=status.HTTP_404_NOT_FOUND
            )

        if user:
            serilizer = userserializers(user)
            user_id = serilizer.data.get("user_id")
            payload = {
                "id": user_id,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
                "iat": datetime.datetime.utcnow(),
            }
            token = jwt.encode(payload, "secret", algorithm="HS256")
            query_params = {"token": token, "email": email, "username": user.username, "country": user.country}
            reset_password_url = settings.RESET_URL_BASE + "?" + urlencode(query_params)

            send_forget_ps_email(email, reset_password_url)
            
            data = {"token": token}
            return Response(data, status=status.HTTP_200_OK)

        return Response(
            {"error": "email is not registered"}, status=status.HTTP_404_NOT_FOUND
        )


class validatet_forgotpassword(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token")
        token = token_str.encode("utf-8")

        try:
            payload = jwt.decode(token, "secret", algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return Response(
                {"Error": "AuthenticationFailed"}, status=status.HTTP_404_NOT_FOUND
            )
        user = User.objects.get(user_id=payload["id"])
        password = request.data.get("password")
        username = request.data.get("username")
        country = request.data.get("country")
        user.password = make_password(password)
        user.username = username
        user.country = country
        user.save()
        data = {"message": f"password changed successfully"}
        return Response(data, status=status.HTTP_200_OK)
