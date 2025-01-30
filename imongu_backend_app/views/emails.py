from django.contrib.auth.hashers import make_password
from rest_framework import status
from imongu_backend_app.models import User,company,employee,team_Table, team_employees, Role
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
import uuid
from django.conf import settings
import jwt,datetime
from urllib.parse import urlencode
from imongu_backend_app.utils.email import *
from imongu_backend_app.utils.jwt import *
from imongu_backend_app.utils.users import * 
from payment.utils import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
from rest_framework.permissions import AllowAny
from imongu_backend.custom_permission.authencation import JWTAuthentication



class Sendemail(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Invite"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
        
        email_id = request.data.get('email')
        employee_role_id = request.data.get('employee_role_id')
        report_to_id = request.data.get('report_to')  # New field to specify reporting manager
        teams = request.data.get('teams', [])

        user = User.objects.filter(email=email_id).first()
        try:
            role_obj = Role.objects.get(id=employee_role_id)
        except Role.DoesNotExist:
            return Response({"error": f"Invalid role ID: {employee_role_id}"}, status=status.HTTP_400_BAD_REQUEST)

        if user:
            user_id = user.user_id
            user.email_verified = True
            user.save()
            # Check if a company with the given company_id exists
            company_instance = company.objects.get(company_id=company_id)
            # Now, add this user to the employee table with role="user"
            try:
                employee_obj = employee.objects.get(user_id = user_id , company_id=company_id)
                return Response({'error': 'Employee already exists with this email'}, status=status.HTTP_404_NOT_FOUND)
            except employee.DoesNotExist:
                # Create employee with report_to field
                report_to_employee = employee.objects.filter(employee_id=report_to_id).first() if report_to_id else None
                employee_obj = employee.objects.create(
                    user_id=user,
                    employee_id=str(uuid.uuid4()),
                    company_id=company_instance,
                    role=role_obj,
                    report_to=report_to_employee
                )

            # Add employee to teams
            for team_id in teams:
                try:
                    team = team_Table.objects.get(team_id=team_id)
                    team_employee = team_employees(
                        team_employees_id=str(uuid.uuid4()),
                        team_id=team,
                        user_id=user,
                        role=role_obj
                    )
                    team_employee.save()
                except team_Table.DoesNotExist:
                    return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)
            # Send an invitation email to the user's email address
            invite_url = settings.LOGIN_BASE_URL
            company_owner_name = company_instance.user_id.username
            send_invite_email(email_id, invite_url,company_owner_name)
            add_user_to_stripe(company_id)
            return Response({"message": "Invitation sent successfully."}, status=status.HTTP_200_OK)
        else:
            # If the user does not exist, create a new user
            password = make_password("1b2e4ed4bce")
            user_name= email_id.split("@")[0]
            new_user = User(email=email_id, password=password, username=user_name,email_verified = True)
            new_user.save()
            # Check if a company with the given company_id exists
            company_instance = company.objects.get(company_id=company_id)
            # Now, add this new user to the employee table
            report_to_employee = employee.objects.filter(employee_id=report_to_id).first() if report_to_id else None
            employee_obj = employee.objects.create(
                user_id=new_user,
                employee_id=str(uuid.uuid4()),
                company_id=company_instance,
                role=role_obj,
                report_to=report_to_employee
            )
            user_id=new_user.user_id
            # create_free_trial_subscription(user_id, email_id)
            # add employee into teams
            for team_id in teams:
                try:
                    team = team_Table.objects.get(team_id = team_id)
                    team_employee = team_employees(
                        team_employees_id=str(uuid.uuid4()),
                        team_id=team,
                        user_id=new_user,
                        role=role_obj
                    )
                    team_employee.save()
                except team_Table.DoesNotExist:
                    return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)
            payload={
                'id':user_id,
                'exp':datetime.datetime.utcnow()+datetime.timedelta(days=1),
                'iat':datetime.datetime.utcnow()
            }
            token=jwt.encode(payload,'secret',algorithm='HS256')    
            query_params = {"token" : token , "user_id" : user_id}
            invite_url = settings.RESET_URL_BASE + '?' + urlencode(query_params)       
            # Send an invitation email to the new user's email address
            company_owner_name = company_instance.user_id.username
            send_invite_email(email_id, invite_url,company_owner_name)
            # add user to stripe on company owner account for billing (pay per seat model)
            add_user_to_stripe(company_id)
            return Response({"message": "Invitation sent successfully."}, status=status.HTTP_200_OK)

class verifyEmail(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self,request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist :
            return Response({"error": "Invalid email ID"}, status=status.HTTP_404_NOT_FOUND)

        if user.email_verified == True:
            return Response({'message' : 'Email already Verified'},status=status.HTTP_200_OK) 

        user_id = user.user_id
        verify_token , verify_url = generate_varification_token_and_url(user_id)
        user.verify_token = verify_token
        user.save()
        send_verify_token_email(email, verify_url)

        return Response({'message': 'Verification Email has been sent to your email address.'},status=status.HTTP_200_OK)

class verifyEmailToken(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self,request):
        token = request.data.get('verify_token')
        user_id = request.data.get('user_id')
        user = User.objects.get(user_id=user_id)
        old_token = user.verify_token
        new_user = verify_email_token(token,user)
        if new_user and old_token == token:
            data = get_verified_user_details(user)
            access_token = JWTAuthentication.create_jwt(str(user.user_id))
            data['access_token'] = access_token
            # Set access_token in cookies
            response = Response(data, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,  # JavaScript can't access this cookie
                secure=True,    # Only sent over HTTPS
                samesite='Lax'  # CSRF protection
            )

            new_user.email_verified = True
            new_user.save()
            return response
        else:
            return Response({'error': 'Token not verified. Please resend verification link.'},status=status.HTTP_404_NOT_FOUND)
