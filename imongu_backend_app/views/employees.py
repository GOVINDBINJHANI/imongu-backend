from io import BytesIO
from rest_framework import status
from imongu_backend_app.models import User,employee, team_employees, Role, company
from imongu_backend_app.Serializers import employeeserializers,TeamEmployeeSerializer, EmployeeHierarchySerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.conf import settings
import stripe,json
from urllib.parse import urlparse
from PIL import Image
from imongu_backend_app.utils.s3 import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from django.contrib.auth.models import AnonymousUser
from imongu_backend_app.utils.email import *
from imongu_backend_app.static import GDPR_RESTRICTED_COUNTRIES
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, employee_feature_activity_access, get_all_reportees
from django.core.exceptions import PermissionDenied
from payment.utils import delete_customer_by_stripe

stripe.api_key = settings.STRIPE_API_KEY

class ProfileImage(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        image_file = request.data["profile_image"]
        if image_file:
            s3_url = upload_to_s3(image_file.read())
            return Response({"message": "profile picture uploaded",
                             "image_url": s3_url}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": "profile picture not found"},
                            status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        image_url = request.data["profile_image_url"]
        parsed_url = urlparse(image_url)
        s3_object_key = parsed_url.path[1:]
        if s3_object_key:
            delete_from_s3(s3_object_key)
            return Response({"message": "profile picture deleted"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": "profile picture not found"}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        image_url = request.data["old_image_url"]
        image_file = request.data["profile_image"]
        parsed_url = urlparse(image_url)
        s3_object_key = parsed_url.path[1:]
        if image_file and s3_object_key:
            if delete_from_s3(s3_object_key):
                new_s3_url = upload_to_s3(image_file.read())
                return Response({"message": "profile picture updated", "image_url": new_s3_url},
                                status=status.HTTP_201_CREATED)
            else:
                return Response({"message": "failed to update photo"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"message": "bad request"}, status=status.HTTP_400_BAD_REQUEST)


class employee_details(GenericAPIView):
    permission_classes = [IsValidUser]

    def get_queryset(self, company_id):
        return employee.objects.filter(company_id=company_id)

    def get(self, request):
        company_id = request.query_params.get('company_id')
        empu = GetUserId.get_user_id(request)  
        user_role_id = validate_user_company_access(empu, company_id)
        all_report_to_ids = employee.objects.values_list('report_to', flat=True)

        # Filter the employees based on the team
        fields = request.query_params.get('fields')
        if fields is not None:
            field_dict = json.loads(fields)
        else:
            field_dict = {}

        name = field_dict.get('name')
        email = field_dict.get('email')
        team_ids = field_dict.get('team_ids', [])

        employees = self.get_queryset(company_id)

        # Add filter for employee by name and email
        if name:    
            employees = employees.filter(user_id__username__icontains=name)

        if email:   
            employees = employees.filter(user_id__email__icontains=email)

        serialized_data = []
        if employees:
            for emp in employees:
                serializer = employeeserializers(emp)
                user_id = serializer.data.get("user_id")
                username = emp.user_id.username
                email = emp.user_id.email
                country = emp.user_id.country
                deactivated=emp.deactivated
                updated_serializer_data = serializer.data

                # Getting the employees details along with their teams
                team_employee = team_employees.objects.filter(user_id=user_id).order_by('role')
                teams = []
                employee_teams = []
                team_id_is_manager_mapping = {}

                for team_emp in team_employee:
                    team_emp_serializer = TeamEmployeeSerializer(team_emp)
                    team_name = team_emp.team_id.team_name
                    role = team_emp.role
                    isManager = True if role.role_name == 'Admin' else False
                    team_id = team_emp_serializer.data.get('team_id')
                    comp_id = team_emp.team_id.company_id.company_id

                    if team_id not in team_id_is_manager_mapping and company_id == comp_id:
                        teams.append({"team_name": team_name, "isManager": isManager, "team_id": team_id})
                        employee_teams.append(team_id)
                        team_id_is_manager_mapping[team_id] = True
                updated_serializer_data['teams'] = teams
                updated_serializer_data['username'] = username
                updated_serializer_data['email'] = email
                updated_serializer_data['userstatus'] = deactivated
                updated_serializer_data['profile_image'] = emp.user_id.profile_image

                # Add filter for empployee associated with perticular teams
                if team_ids:
                    employee_teams_set = set(employee_teams)
                    team_ids_set = set(team_ids)
                    if not employee_teams_set.intersection(team_ids_set):
                        continue

                report_to_id = updated_serializer_data.get('report_to')
                if report_to_id:
                    report_to_employee = employee.objects.filter(employee_id=report_to_id).first()
                    updated_serializer_data['report_to_name'] = report_to_employee.user_id.username if report_to_employee else None
                try:
                    has_delete_access = employee_feature_activity_access(
                        role_id=user_role_id,
                        company_id=company_id,
                        feature_name="Employees",
                        activity_name="Delete"
                    )
                    if has_delete_access:
                        can_delete = emp.employee_id not in all_report_to_ids
                        can_deactivate = country in GDPR_RESTRICTED_COUNTRIES
                    else:
                        can_delete = False
                        can_deactivate = False
                except PermissionDenied:
                    can_delete = False
                    can_deactivate = False

                updated_serializer_data['is_delete'] = can_delete
                updated_serializer_data['deactivate'] = can_deactivate                

                serialized_data.append(updated_serializer_data)
        return Response(serialized_data)

    def delete(self,request):
        employee_id=request.query_params.get('employee_id')
        deactivate = request.query_params.get('deactivate', None)
        if not employee_id:
            return Response({"error": "Employee ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            emp = employee.objects.get(employee_id=employee_id)
            user = emp.user_id
            # empu = GetUserId.get_user_id(request)
            # if str(user.user_id) == str(empu):
            #     return Response({"error": "Employee cannot delete/deactivated themselves."}, status=status.HTTP_400_BAD_REQUEST)

            if deactivate is not None:
                emp.deactivated = True if deactivate.lower() == 'true' else False
                emp.save()
                status_message = "deactivated" if emp.deactivated else "activated"
                return Response({'message': f'Employee {status_message} successfully'}, status=status.HTTP_200_OK)
            if user.country in GDPR_RESTRICTED_COUNTRIES:
                return Response(
                    {'error': f"Employee cannot be deleted due to GDPR restrictions in {user.country}. Consider deactivating instead."},
                    status=status.HTTP_403_FORBIDDEN
                )
            # Check can_delete logic
            all_report_to_ids = employee.objects.values_list('report_to', flat=True)
            can_delete = emp.employee_id not in all_report_to_ids

            if not can_delete:
                return Response(
                    {'error': "Employee cannot be deleted because they are referenced in the reporting hierarchy."},
                    status=status.HTTP_403_FORBIDDEN
                )

            com_id = emp.company_id
            user_id = emp.user_id
            team_employees.objects.filter(team_id__company_id = com_id , user_id = user_id).delete()
            emp.delete()
            is_emp = employee.objects.filter(user_id=user_id)
            if not is_emp:
                user =User.objects.get(user_id=user_id.user_id) 
                delete_customer_by_stripe(user.email)
                user.delete()
            return Response({'message': 'Employees deleted successfully'}, status=status.HTTP_202_ACCEPTED)
        except employee.DoesNotExist:
            return Response({'error': 'Employees not found'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {"error": "employee_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_record = employee.objects.get(employee_id=employee_id)
            user = employee_record.user_id  
            if not employee_record.deactivated:
                return Response(
                    {"message": "Employee account is already active."},
                    status=status.HTTP_200_OK,
                )

            employee_record.deactivated = False
            employee_record.save()
            send_activation_email(user.email)

            return Response(
                {"message": "Employee account has been successfully activated."},
                status=status.HTTP_200_OK,
            )

        except employee.DoesNotExist:
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HigherLevelEmployeeAPIView(APIView):
    def post(self, request):
        try:
            company_id = request.data.get('company_id')
            
            if not company_id:
                return Response({"error": "company_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                company_obj = get_object_or_404(company, company_id=company_id)
            except company.DoesNotExist:
                return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

            all_employees = employee.objects.filter(
                company_id=company_obj
            ).select_related('user_id', 'role')

            all_employee_data = [
                {
                    'employee_id': emp.employee_id,
                    'name': emp.user_id.username,
                    'role_name': emp.role.role_name
                }
                for emp in all_employees
            ]

            return Response(all_employee_data, status=status.HTTP_200_OK)

        except DatabaseError as e:
            return Response({"error": "Database error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def put(self, request):
    
        try:
            employee_id = request.data.get('employee_id')
            report_to_id = request.data.get('report_to')
            role_id = request.data.get('role_id') 

            if not employee_id:
                return Response({"error": "employee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                employee_obj = employee.objects.get(employee_id=employee_id)
            except employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

            report_to_employee = None
            if report_to_id:
                try:
                    report_to_employee = employee.objects.get(employee_id=report_to_id)
                except employee.DoesNotExist:
                    return Response({"error": "report_to employee not found"}, status=status.HTTP_404_NOT_FOUND)
                
                if employee_id == report_to_id:
                    return Response({"error": "An employee cannot report to themselves"}, status=status.HTTP_400_BAD_REQUEST)
                
                employee_obj.report_to = report_to_employee
            else:
                employee_obj.report_to = None

            if role_id:
                try:
                    role_obj = Role.objects.get(id=role_id)
                    employee_obj.role = role_obj
                except Role.DoesNotExist:
                    return Response({"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND)
            
            employee_obj.save()

            response_data = {
                "message": "report_to and role fields updated successfully",
                "employee_id": employee_id,
                "new_report_to": report_to_id,
                "report_to_name": report_to_employee.user_id.username if report_to_employee else None,
                "new_role_id": role_id,
                "new_role_name": role_obj.role_name if role_id else None
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except DatabaseError as e:
            return Response({"error": "Database error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            company_id = request.query_params.get('company_id')
            excluded_employee_id = request.query_params.get('employee_id') 

            if not company_id:
                return Response({"error": "company_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not excluded_employee_id:
                return Response({"error": "employee_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            company_obj = get_object_or_404(company, company_id=company_id)
            excluded_employee = employee.objects.filter(
                employee_id=excluded_employee_id,
                company_id=company_obj
            ).first()

            if not excluded_employee:
                return Response({"error": "Excluded employee not found in the company"}, status=status.HTTP_404_NOT_FOUND)

            excluded_employees = get_all_reportees(excluded_employee)
            all_employees = employee.objects.filter(
                company_id=company_obj
            ).exclude(employee_id__in=excluded_employees).select_related('user_id', 'role')

            all_employee_data = [
                {
                    'employee_id': emp.employee_id,
                    'name': emp.user_id.username,
                    'role_name': emp.role.role_name
                }
                for emp in all_employees
            ]

            return Response(all_employee_data, status=status.HTTP_200_OK)

        except DatabaseError as e:
            return Response({"error": "Database error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeHierarchyView(GenericAPIView):
    permission_classes = [IsValidUser]
    
    def get(self, request):
        try:
            company_id = request.query_params.get('company_id')
            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            top_level_employees = employee.objects.filter(company_id=company_id, report_to__isnull=True)
            
            if not top_level_employees.exists():
                return Response({"error": "No employees found for the given company."}, status=status.HTTP_404_NOT_FOUND)

            all_children = []
            for emp in top_level_employees:
                children = employee.objects.filter(report_to=emp)
                all_children.extend(children)

            user_id = request.user.user_id if not isinstance(request.user, AnonymousUser) else None
            serialized_data = EmployeeHierarchySerializer(
                all_children,  
                many=True, 
                context={'user_id': user_id}
            ).data
            return Response(serialized_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
