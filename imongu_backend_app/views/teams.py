from rest_framework import status
from imongu_backend_app.models import User,company,team_Table, team_employees, Role
from imongu_backend_app.Serializers import TeamEmployeeSerializer,TeamSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.db import IntegrityError, transaction
import json,uuid
from imongu_backend_app.utils.notification import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.views import APIView
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
from django.shortcuts import get_object_or_404

class AddUserToTeam(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        company_id = request.data.get('company_id')
        team_name = request.data.get('team_name')
        users = request.data.get('users', [])
        login_user_id = GetUserId.get_user_id(request)

        feature_name = request.resolver_match.url_name
        activity_name = "Create"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)



        try:
            company_obj = company.objects.get(company_id=company_id)
        except company.DoesNotExist:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

        # Create a new team with a unique team_id
        team_id = str(uuid.uuid4())
        team = team_Table.objects.create(team_id=team_id, company_id=company_obj, team_name=team_name)
        assign_ids = User.objects.filter(company__company_id=company_id).values_list('user_id', flat=True)

        # Validate user IDs and add them to the team
        for user in users:
            try:
                user_id = user.get("user_id")
                role_id = user.get("role_id")
                user = User.objects.get(user_id=user_id)
                role = Role.objects.get(id=role_id)
                # Create an instance of team_employees with a unique team_employees_id, team_id, user_id, and role
                team_employee = team_employees(team_employees_id=str(uuid.uuid4()), team_id=team, user_id=user, role=role)
                team_employee.save()
            except User.DoesNotExist:
                return Response({"error": "No valid users added to the team"}, status=status.HTTP_400_BAD_REQUEST)

        
        # Serialize and return the updated team with added users
        serializer = TeamSerializer(team)
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            message = user.username + " created the team "
            changes = {}
            changes['company_id'] = str(company_id)
            save_notification(company_id, message, user, "team", title=team.team_name, changes=changes)
            
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        team_id = request.data.get('team_id')
        new_team_name = request.data.get('team_name', '')
        users = request.data.get('users', None)  # None to distinguish if it's provided or empty
        login_user_id = GetUserId.get_user_id(request)
        changes = {}

        try:
            team = team_Table.objects.get(team_id=team_id)
            company_id = team.company_id.company_id  # Get company_id from team
            assign_ids = employee.objects.filter(company_id=company_id).values_list('user_id', flat=True)
        except team_Table.DoesNotExist:
            return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)

        feature_name = request.resolver_match.url_name
        activity_name = "Update"
        role_id = validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        # Update the team name
        if new_team_name:
            changes['team_name'] = new_team_name
            team.team_name = new_team_name
            team.save()

        # Update team members based on the provided 'users' list
        if users is not None:
            # If the 'users' list is empty, remove all existing team members
            if not users:
                team_employees.objects.filter(team_id=team_id).delete()
                changes['members'] = []
                print("All members removed")
            else:
                old_employees = team_employees.objects.filter(team_id=team_id).select_related('user_id')
                old_user_ids = set(old_employees.values_list('user_id__user_id', flat=True))
                new_user_ids = {user['user_id'] for user in users}
                user_ids_to_remove = old_user_ids - new_user_ids
                user_ids_to_create = new_user_ids - old_user_ids

                # Remove users that are no longer in the team
                if user_ids_to_remove:
                    team_employees.objects.filter(user_id__user_id__in=user_ids_to_remove, team_id=team_id).delete()

                new_employees = []
                for user_data in users:
                    if user_data['user_id'] in user_ids_to_create:
                        try:
                            user = User.objects.get(user_id=user_data['user_id'])
                            role = Role.objects.get(id=user_data['role_id'])
                            if user.user_id in assign_ids:
                                team_employee = team_employees(
                                    team_employees_id=str(uuid.uuid4()),
                                    team_id=team,
                                    user_id=user,
                                    role=role
                                )
                                new_employees.append(team_employee)
                            else:
                                return Response(
                                    {"error": f"User with id {user_data['user_id']} does not belong to the company"},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except User.DoesNotExist:
                            return Response(
                                {"error": f"User with id {user_data['user_id']} does not exist"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except Role.DoesNotExist:
                            return Response(
                                {"error": f"Role with id {user_data['role_id']} does not exist"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                # Save new employees
                if new_employees:
                    team_employees.objects.bulk_create(new_employees)

                new_members = [{'username': user.user_id.username, 'profile_image': user.user_id.profile_image, "type": user.role.role_name} 
                            for user in team_employees.objects.filter(team_id=team_id).select_related('user_id', 'role')]
                changes['members'] = new_members

        serializer = TeamSerializer(team)
        if login_user_id:
            try:
                user = User.objects.get(user_id=login_user_id)
                message = user.username + " updated the team "
                changes['team_id'] = str(team_id)
                save_notification(company_id, message, user, "team", title=team.team_name, changes=changes)
            except User.DoesNotExist:
                return Response({"error": "Login user not found"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_200_OK)

    
    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id') 
        fields = request.query_params.get('fields')
        role_id = validate_user_company_access(user_id, company_id)
        role_name = get_object_or_404(Role, id=role_id).role_name

        if fields is not None:
            field_dict = json.loads(fields)
        else:
            field_dict = {}

        team_name = field_dict.get('team_name')
        teams = team_Table.objects.filter(company_id=company_id).order_by('team_name')

        if team_name:
            teams = teams.filter(team_name__icontains=team_name)
        all_teams = []
        for team in teams:
            data = {}
            team_id = team.team_id
            team_employee = team_employees.objects.filter(team_id=team_id)

            if role_name != "Admin":
                if not team_employee.filter(user_id=user_id).exists():
                    continue  

            serializer = TeamEmployeeSerializer(team_employee, many=True)
            data['team_name'] = team.team_name
            data['team_id'] = team_id
            data['employees'] = [{"username":  user.user_id.username, "profile_image" : user.user_id.profile_image,**employee} for employee , user in zip(serializer.data ,team_employee )]

            all_teams.append(data)

        return Response(all_teams, status=status.HTTP_200_OK)
    
    def delete(self, request):
        team_id = request.query_params.get('team_id')
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')
        assign_ids = User.objects.filter(company__company_id=company_id).values_list('user_id', flat=True)

        feature_name = request.resolver_match.url_name
        activity_name = "Delete"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        try:
            team = team_Table.objects.get(team_id=team_id)
        except team_Table.DoesNotExist:
            return Response({"error": "Team not found"}, status=status.HTTP_404_NOT_FOUND)
        changes = {'userOwners': {'oldValue': [], 'newValue': []}}
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            company_id = team.company_id.company_id
            message = user.username + " deleted the team "
            old_value = {'username': user.username, 'profile_image': user.profile_image, 'type': 'user'}
            changes['userOwners']['oldValue'].append(old_value)
            save_notification(company_id, message, user, "team", title=team.team_name, changes=changes, isDeleted=True)
            changes['userOwners']['newValue'] = None
        try:
            team_employees.objects.filter(team_id=team_id).delete()
            team.delete()
            return Response({"message": "Team and associated users deleted successfully"}, status=status.HTTP_202_ACCEPTED)
        except IntegrityError as e:
            return Response({"error": f"Error deleting rows: {e}"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error":f"An unexpected error occurred: {e}"}, status=status.HTTP_404_NOT_FOUND)

class TeamColabView(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        user_id = GetUserId.get_user_id(request)
        employee_user_id = request.data.get('employee_user_id')
        team_id = request.data.get('team_id')
        company_id = request.data.get('company_id')

        # Validate input
        if not all([employee_user_id, company_id]):
            return Response({"error": "Employee ID and Company ID are required."}, status=status.HTTP_400_BAD_REQUEST)
        user_role_id = validate_user_company_access(user_id, company_id)

        # Validate user's access to the company
        employee_role_id = validate_user_company_access(employee_user_id, company_id)
        
        # Validate feature access
        feature_name = request.resolver_match.url_name
        activity_name = "Invite"
        validate_feature_activity_access(user_role_id, company_id, feature_name, activity_name)

        # Get the employee
        employee_obj = get_object_or_404(employee, user_id=employee_user_id, company_id=company_id, role_id =employee_role_id )
        e_role=get_object_or_404(Role, id=employee_role_id)

        if team_id:
            # If team_id is provided, add employee to the team
            team = get_object_or_404(team_Table, team_id=team_id, company_id=company_id)
            
            # Check if the employee is already in the team
            if team_employees.objects.filter(team_id=team, user_id=employee_obj.user_id, role=employee_role_id).exists():
                return Response({"error": "Employee is already in the team."}, status=status.HTTP_400_BAD_REQUEST)

            # Add employee to the team
            team_employee = team_employees.objects.create(
                team_employees_id=str(uuid.uuid4()),
                team_id=team,
                user_id=employee_obj.user_id,
                role=e_role

            )
            
            return Response({"message": "Employee added to the team successfully."}, status=status.HTTP_201_CREATED)
        else:
            # If team_id is not provided, just return success (employee is already associated with the company)
            return Response({"message": "Employee is associated with the company."}, status=status.HTTP_200_OK)
