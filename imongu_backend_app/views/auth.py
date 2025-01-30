from django.contrib.auth.hashers import make_password, check_password
from rest_framework import status
from imongu_backend_app.models import User, company, employee, Room, Role, RoleAccess, Activity, Feature
from imongu_backend_app.Serializers import userserializers
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid
from django.db import IntegrityError
from django.conf import settings
from imongu_backend_app.utils.email import *
from imongu_backend_app.utils.jwt import *
from imongu_backend_app.utils.users import *
from imongu_backend.custom_permission.authencation import JWTAuthentication
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.views import APIView
import jwt 


class login(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.data.get("provider") == "google":
            client_id = settings.CLIENT_ID
            google_token = request.data.get("credential")
            idinfo = id_token.verify_oauth2_token(
                google_token, requests.Request(), client_id
            )
            username = idinfo["name"]
            email = idinfo["email"]
            user = User.objects.filter(email=email).first()
            if user:
                employees = employee.objects.filter(user_id=user)
                if employees.exists():
                    active_employees = employees.filter(deactivated=False)
                    
                    if active_employees.exists():
                        employee_record = active_employees.first()
                        company_record = employee_record.company_id
                        admin_email = company_record.user_id.email
                    else:
                        return Response(
                            {
                                "error": "Your account has been deactivated. Please contact your admin to activate your account.",
                                "deactivated": True,
                                "user_email": user.email,
                                "admin_email":admin_email
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

                user.email_verified = True
                user.save()
                # we are getting the details like company and employees and plan
                updated_serializer_data = get_verified_user_details(user)
                access_token = JWTAuthentication.create_jwt(str(user.user_id))
                updated_serializer_data['access_token'] = access_token
                response = Response(updated_serializer_data, status=status.HTTP_200_OK)
                # Set token in cookies
                response.set_cookie(
                    key='access_token',
                    value=access_token,
                    httponly=True,  # Protects the cookie from being accessed via JavaScript
                    secure=True,    # Ensures the cookie is only sent over HTTPS
                    samesite='Lax'  # Protects against CSRF
                )
                return response
            else:
                return Response(
                    {"error": "User with this email doesn't exists"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        else:
            email = request.data.get("email")
            password = request.data.get("password")
            username = request.data.get("username")
            user = User.objects.filter(email=email).first()   
            if user:
                employees = employee.objects.filter(user_id=user)
                if employees.exists():
                    active_employees = employees.filter(deactivated=False)
                    
                    if active_employees.exists():
                        employee_record = active_employees.first()
                        company_record = employee_record.company_id
                    else:
                        employee_record = employees.first()  
                        company_record = employee_record.company_id
                        admin_email = company_record.user_id.email
                        return Response(
                            {
                                "error": "Your account has been deactivated. Please contact your admin to activate your account.",
                                "deactivated": True,
                                "user_email": user.email,
                                "admin_email":admin_email
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

                if check_password(password, user.password):
                    updated_serializer_data = get_verified_user_details(user)
                    access_token = JWTAuthentication.create_jwt(str(user.user_id))
                    updated_serializer_data['access_token'] = access_token
                    # Create the response object
                    response = Response(updated_serializer_data, status=status.HTTP_200_OK)
                    # Set the access token in a cookie
                    response.set_cookie(
                        key='access_token',
                        value=access_token,
                        httponly=True,  # JavaScript can't access this cookie
                        secure=True,    # Only sent over HTTPS
                        samesite='Lax'  # CSRF protection
                    )
                    
                    # Verify email if not already verified
                    if not user.email_verified:
                        verify_token, verify_url = generate_varification_token_and_url(
                            user.user_id
                        )
                        user.verify_token = verify_token
                        user.save()
                        send_verify_token_email(email, verify_url)
                        return Response(
                            {
                                "error": "Email not verified. Verification email has been sent to your email address."
                            },
                            status=status.HTTP_401_UNAUTHORIZED,
                        )
                    
                    return response
                else:
                    return Response(
                        {"error": "Invalid Password"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
            else:
                return Response(
                    {"error": "User with this email doesn't exist"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

class Signup(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.data.get("provider") == "google":
            client_id = settings.CLIENT_ID
            google_token = request.data.get("credential")
            idinfo = id_token.verify_oauth2_token(
                google_token, requests.Request(), client_id
            )
            username = idinfo["name"]
            email = idinfo["email"]
            profile_image = idinfo.get("picture", "")
            company_name = request.data.get("company_name", "")
            country_name = idinfo.get("country", "United States of America")
            try:
                user = User.objects.create(
                    email=email, username=username, profile_image=profile_image, country=country_name
                )
                user = User.objects.latest("user_id")
            except IntegrityError:
                return Response(
                    {"error": "User with this email already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company_id = str(uuid.uuid4())
            employee_id = str(uuid.uuid4())
            role_name = "Admin"
            Company = company.objects.create(
                user_id=user, company_id=company_id, company_name=company_name
            )
            existing_role_access = RoleAccess.objects.filter(company=Company).first()
            if not existing_role_access:
                # Create a new role
                role,created = Role.objects.get_or_create(role_name=role_name)

                # Fetch all features
                features = Feature.objects.all()

                # Initialize RoleAccess entries
                role_access_entries = []

                for feature in features:
                    # Fetch activities associated with the current feature
                    feature_activities = Activity.objects.filter(feature=feature)

                    for activity in feature_activities:
                        role_access_entry = RoleAccess(
                            role=role,
                            feature=feature,
                            activity=activity,
                            company=Company,
                            activity_status=True
                        )
                        role_access_entries.append(role_access_entry)

                # Bulk create all RoleAccess entries
                RoleAccess.objects.bulk_create(role_access_entries)
            Employee = employee.objects.create(
                user_id=user, employee_id=employee_id, role=role, company_id=Company
            )
            Room.objects.create(user_id=user, company_id=Company)
            create_free_trial_subscription(user.user_id, Company)
            # we are getting the details like company and employees and plan
            updated_serializer_data = get_verified_user_details(user)
            access_token = JWTAuthentication.create_jwt(str(user.user_id))
            updated_serializer_data['access_token'] = access_token
            user.verify_token = True
            user.save()
            
            # Set access_token in cookies
            response = Response(updated_serializer_data, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,  # JavaScript can't access this cookie
                secure=True,    # Only sent over HTTPS
                samesite='Lax'  # Protects against CSRF
            )
            return response
        else:
            serilizer = userserializers(data=request.data)
            if serilizer.is_valid():
                email = request.data.get("email")
                password = request.data.get("password")
                username = request.data.get("username")
                profile_image = request.data.get("profile_image")
                company_name = request.data.get("company_name")
                country = request.data.get("country")
                hash_password = make_password(password)
                try:
                    user = User.objects.create(
                        email=email,
                        password=hash_password,
                        username=username,
                        profile_image=profile_image,
                        country=country,
                    )
                    user = User.objects.latest("user_id")
                except IntegrityError:
                    return Response(
                        {"error": "User with this email already exists."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                updated_serializer_data = {}
                company_id = str(uuid.uuid4())
                employee_id = str(uuid.uuid4())
                role_name = "Admin"
                Company = company.objects.create(
                    user_id=user, company_id=company_id, company_name=company_name
                )
                existing_role_access = RoleAccess.objects.filter(company=Company).first()
                if not existing_role_access:
                    # Create a new role
                    role,created = Role.objects.get_or_create(role_name=role_name)

                    # Fetch all features
                    features = Feature.objects.all()

                    # Initialize RoleAccess entries
                    role_access_entries = []

                    for feature in features:
                        # Fetch activities associated with the current feature
                        feature_activities = Activity.objects.filter(feature=feature)

                        for activity in feature_activities:
                            role_access_entry = RoleAccess(
                                role=role,
                                feature=feature,
                                activity=activity,
                                company=Company,
                                activity_status=True
                            )
                            role_access_entries.append(role_access_entry)

                    # Bulk create all RoleAccess entries
                    RoleAccess.objects.bulk_create(role_access_entries)
                Employee = employee.objects.create(
                    user_id=user, employee_id=employee_id, role=role, company_id=Company
                )
                user_id = user.user_id
                Room.objects.create(user_id=user, company_id=Company)
                create_free_trial_subscription(user_id, Company)
                # varifing user
                user_obj = User.objects.get(user_id=user_id)
                verify_token, verify_url = generate_varification_token_and_url(user_id)
                user_obj.verify_token = verify_token
                user_obj.save()
                send_verify_token_email(email, verify_url)
                # notification_message = " Your User signup was successful."
                # Notification.objects.create(user=user, message=notification_message)
                # utils.send_notification(self, message= notification_message, room_name=company_name)
                updated_serializer_data["message"] = (
                    "Verification Email has been sent to your email address."
                )
                access_token = JWTAuthentication.create_jwt(str(user_obj.user_id))
                updated_serializer_data['access_token'] = access_token
                # Set access_token in cookies
                response = Response(updated_serializer_data, status=status.HTTP_200_OK)
                response.set_cookie(
                    key='access_token',
                    value=access_token,
                    httponly=True,  # JavaScript can't access this cookie
                    secure=True,    # Only sent over HTTPS
                    samesite='Lax'  # CSRF protection
                )
                return response
            else:
                data = serilizer.errors
                invalid_email = data.get('email', None)
                if invalid_email:
                    return Response({"error": "Account already exist with this email."}, status=status.HTTP_400_BAD_REQUEST)
                return Response(serilizer.errors, status=status.HTTP_400_BAD_REQUEST)
class ProfileEdit(GenericAPIView):
    permission_classes = [AllowAny]

    def put(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        username = request.data.get("username", "").strip()
        company_name = request.data.get("company_name", "").strip()
        profile_image = request.data.get("profile_image", "")
        country = request.data.get("country", "")
        if username:
            if username == "":
                return Response({"error": "Username cannot be empty or spaces."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(user_id=user_id)
            company_obj = company.objects.get(company_id=company_id)

        except company.DoesNotExist:
            return Response(
                {"error": "Company not found with this ID"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except User.DoesNotExist:
            return Response(
                {"error", "User not found with this email "},
                status=status.HTTP_404_NOT_FOUND,
            )

        if username:
            user.username = username
            user.save()

        if company_name:
            company_obj.company_name = company_name
            company_obj.save()

        if profile_image:
            user.profile_image = profile_image
            user.save()

        if country:
            user.country = country
            user.save()

        updated_serializer_data = get_verified_user_details(user)
        return Response(updated_serializer_data, status=status.HTTP_200_OK)


class ContactViews(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name", "")
        email = request.data.get("email", "")
        content = request.data.get("content", "")
        phone_number = request.data.get("phone_number", "")
        company_name = request.data.get("company_name", "")

        send_enquiry_email(name, email, phone_number, company_name, content)

        return Response(
            {"message": "Email sent successfully"}, status=status.HTTP_200_OK
        )
    
    def delete(self, request):
        email = request.data.get("email", "")
        user = User.objects.get(email=email)
        user.delete()
        return Response(
            {"message": "User deleted successfully"}, status=status.HTTP_200_OK
        )

class LogoutView(APIView):
    def post(self, request):
        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        
        # Remove the JWT token by setting an expired cookie
        response.delete_cookie('access_token')
        
        return response

class ReactivateAccountAPI(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_email = request.data.get("user_email")
        admin_email = request.data.get("admin_email")

        if not user_email or not admin_email:
            return Response(
                {"error": "Both user_email and admin_email are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Fetch the user requesting reactivation
            user = User.objects.filter(email=user_email).first()
            if not user:
                return Response(
                    {"error": "User email is not registered."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get admin user
            admin_user = User.objects.filter(email=admin_email).first()
            if not admin_user:
                return Response(
                    {"error": "Admin email is not registered."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Generate token for admin reactivation link
            admin_serializer = userserializers(admin_user)
            admin_user_id = admin_serializer.data.get("user_id")

            payload = {
                "id": admin_user_id,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=180),
                "iat": datetime.datetime.utcnow(),
            }
            token = jwt.encode(payload, "secret", algorithm="HS256")

            query_params = {"token": token}
            reactivation_url = settings.REACTIVATION_URL_BASE + "?" + urlencode(query_params)

            # Send reactivation email to the admin
            send_reactivation_email(user.username, user.email, admin_email, reactivation_url)

            return Response(
                {
                    "message": "Reactivation request sent to admin.",
                    "user_email": user_email,
                    "admin_email": admin_email,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
