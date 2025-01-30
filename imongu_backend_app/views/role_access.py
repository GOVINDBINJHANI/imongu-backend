from rest_framework import viewsets
from imongu_backend_app.models import Role, Feature, Activity, RoleAccess, User, company, employee
from imongu_backend_app.Serializers import RoleSerializer, RoleFeatureActivitySerializer, FeatureSerializer, ActivitySerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import connection
from django.db import transaction
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access



class RoleAPIView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')
        role_id = request.query_params.get('role_id')


        # Get the user's role ID in the company (to check if they are Admin)
        user_role_id = validate_user_company_access(user_id, company_id)

        # Retrieve the user's role based on the user_role_id
        user_role = get_object_or_404(Role, id=user_role_id)

        # Check if the user's role is not "Admin"
        # if user_role.role_name != 'Admin':
        #     return Response(
        #         {"error": "This feature is only accessible to Admins."},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        get_object_or_404(User, user_id=user_id)

        # Handle the scenario where company_id and user_id are provided
        if company_id and not role_id:
            # Fetch role IDs and role names associated with the company
            roles = RoleAccess.objects.filter(company_id=company_id).select_related('role').values('role_id', 'role__role_name').distinct()
            roles_data = []

            for role in roles:
                role_id = role['role_id']
                role_name = role['role__role_name']

                # Check if the role can be deleted
                if role_name == 'Admin':
                    is_delete = False
                else:
                    # Check in the Employee table if any user exists with the role_id
                    is_delete = not employee.objects.filter(role_id=role_id).exists()
                
                roles_data.append({
                    "role_id": role_id,
                    "role_name": role_name,
                    "is_delete": is_delete
                })

            return Response(roles_data, status=status.HTTP_200_OK)

        # Handle the scenario where company_id, user_id, and role_id are provided
        elif company_id and role_id:
            # Fetch feature and activity details associated with the role and company
            role_access_entries = RoleAccess.objects.filter(role_id=role_id, company_id=company_id).select_related('feature', 'activity')
            features_dict = {}

            for entry in role_access_entries:
                feature_id = entry.feature.id
                feature_name = entry.feature.feature_name

                # Group activities under each feature
                if feature_id not in features_dict:
                    features_dict[feature_id] = {
                        "feature_id": feature_id,
                        "feature_name": feature_name,
                        "activities": []
                    }

                features_dict[feature_id]["activities"].append({
                    "activity_id": entry.activity.id,
                    "activity_name": entry.activity.activity_name,
                    "activity_status": entry.activity_status
                })

            # Convert features_dict to a list of grouped features
            grouped_features = list(features_dict.values())

            return Response(grouped_features, status=status.HTTP_200_OK)

        # If only role_id is provided without company_id, return the specific role details
        if role_id:
            role_obj = get_object_or_404(Role, id=role_id)
            serializer = RoleSerializer(role_obj)
            return Response(serializer.data)

        # If no specific filters are given, return all roles
        roles = Role.objects.all()
        serializer = RoleSerializer(roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')
        role_name = request.data.get('role_name')

        # Get the user's role ID in the company (to check if they are Admin)
        user_role_id = validate_user_company_access(user_id, company_id)

        # Retrieve the user's role based on the user_role_id
        user_role = get_object_or_404(Role, id=user_role_id)

        if role_name == "Admin":
            return Response({"error": "Can't create duplicate name Admin."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the user's role is not "Admin"
        if user_role.role_name != 'Admin':
            return Response(
                {"error": "This feature is only accessible to Admins."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not user_id or not company_id:
            return Response({"error": "User ID and Company ID are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, user_id=user_id)
        company_obj = get_object_or_404(company, company_id=company_id)

        # Since we're removing parent_role, we no longer need to check for it
        if not role_name:
            return Response({"error": "Role name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and save the role without parent_role
        if serializer.is_valid():
            role = serializer.save()  # Save the role without parent_role

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
                        company=company_obj,
                        activity_status=True
                    )
                    role_access_entries.append(role_access_entry)

            # Bulk create all RoleAccess entries
            RoleAccess.objects.bulk_create(role_access_entries)

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def put(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')
        role_id = request.data.get('role_id')
        updates = request.data.get('updates')  # List of updates
        role_name = request.data.get('role_name')

        # Get the user's role ID in the company (to check if they are Admin)
        user_role_id = validate_user_company_access(user_id, company_id)

        # Retrieve the user's role based on the user_role_id
        user_role = get_object_or_404(Role, id=user_role_id)


        # Check if the user's role is not "Admin"
        if user_role.role_name != 'Admin':
            return Response(
                {"error": "This feature is only accessible to Admins."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if required fields are present
        if not user_id or not role_id :
            return Response(
                {"error": "User ID, Role ID are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If "updates" are provided, handle the update of RoleAccess entries
        if updates:
            if not company_id:
                return Response(
                    {"error": "Company ID is required when updates are provided."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate user and company existence
            user = get_object_or_404(User, user_id=user_id)  # Corrected from user_id=user_id to id=user_id
            company_obj = get_object_or_404(company, company_id=company_id)  # Corrected from company_id=company_id to id=company_id

            # Collect all update data for bulk update
            role_access_updates = []

            try:
                updated_ids = []
                with transaction.atomic():
                    for update in updates:
                        feature_id = update.get('feature_id')
                        activity_id = update.get('activity_id')
                        activity_status = update.get('activity_status', True)  # Default to True if not provided

                        # Ensure required fields are present for each update
                        if not feature_id or not activity_id:
                            return Response(
                                {"error": "Feature ID and Activity ID are required for each update."},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        # Fetch the RoleAccess entry
                        role_access = get_object_or_404(
                            RoleAccess,
                            role_id=role_id,
                            feature_id=feature_id,
                            activity_id=activity_id,
                            company=company_obj
                        )

                        # Update the activity status and add to batch
                        role_access.activity_status = activity_status
                        role_access_updates.append(role_access)
                        updated_ids.append(role_access.id)

                    # Bulk update all role access entries
                    RoleAccess.objects.bulk_update(role_access_updates, ['activity_status'])
                
                # Serialize the updated RoleAccess entries to return them
                updated_role_access_entries = RoleAccess.objects.filter(id__in=updated_ids)
                serializer = RoleFeatureActivitySerializer(updated_role_access_entries, many=True)

                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # If "role_name" is provided, update the role's name
        elif role_name:
            try:
                role = get_object_or_404(Role, id=role_id)  # Fetch the Role object
                role.role_name = role_name  # Update the role name
                role.save()  # Save the updated role

                # Serialize and return the updated role
                serializer = RoleSerializer(role)
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # If neither "updates" nor "role_name" is provided, return an error
        else:
            return Response(
                {"error": "Either 'updates' or 'role_name' must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request):
        # Retrieve necessary parameters from query params
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')
        role_id = request.query_params.get('role_id')

        # Get the user's role ID in the company (to check if they are Admin)
        user_role_id = validate_user_company_access(user_id, company_id)

        # Retrieve the user's role based on the user_role_id
        user_role = get_object_or_404(Role, id=user_role_id)

        # Check if the user's role is not "Admin"
        if user_role.role_name != 'Admin':
            return Response(
                {"error": "This feature is only accessible to Admins."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate the presence of required parameters
        if not all([user_id, company_id, role_id]):
            return Response(
                {"error": "User ID, Company ID, and Role ID are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate user and company existence
        # get_object_or_404(User, id=user_id)
        get_object_or_404(company, company_id=company_id)

        # Validate role existence
        role_obj = get_object_or_404(Role, id=role_id)

        # Delete related RoleAccess entries and role
        role_access_deleted_count, _ = RoleAccess.objects.filter(role_id=role_id, company_id=company_id).delete()
        role_obj.delete()

        # Return the count of deleted RoleAccess entries
        return Response(
            {"message": f"Role and {role_access_deleted_count} related RoleAccess entries deleted successfully."},
            status=status.HTTP_200_OK
        )

class FeatureAPIView(APIView):

    def get(self, request):
        # Fetch a specific feature if 'feature_id' is provided, otherwise fetch all features
        feature_id = request.query_params.get('feature_id')
        if feature_id:
            try:
                feature_obj = Feature.objects.get(id=feature_id)
                serializer = FeatureSerializer(feature_obj)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Feature.DoesNotExist:
                return Response({'error': 'Feature not found'}, status=status.HTTP_404_NOT_FOUND)
        features = Feature.objects.all()
        serializer = FeatureSerializer(features, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # Create a new feature
        serializer = FeatureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        # Update an existing feature using 'feature_id'
        feature_id = request.data.get('feature_id')
        if not feature_id:
            return Response({'error': 'ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            feature_obj = Feature.objects.get(id=feature_id)
        except Feature.DoesNotExist:
            return Response({'error': 'Feature not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = FeatureSerializer(feature_obj, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        # Delete a feature using 'feature_id'
        feature_id = request.query_params.get('feature_id')
        if not feature_id:
            return Response({'error': 'ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            feature_obj = Feature.objects.get(id=feature_id)
            feature_obj.delete()
            return Response({'error': 'Feature deleted'},status=status.HTTP_201_CREATED)
        except Feature.DoesNotExist:
            return Response({'error': 'Feature not found'}, status=status.HTTP_404_NOT_FOUND)


class ActivityAPIView(APIView):
    
    def post(self, request):
        # Ensure that 'feature_id' is included in the request data
        feature_id = request.data.get('feature_id')
        activities = request.data.get('activities')
        
        if not feature_id:
            return Response({'error': 'Feature ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not activities or not isinstance(activities, list):
            return Response({'error': 'Activities list is required and should be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate the feature existence
        feature = get_object_or_404(Feature, id=feature_id)
        
        created_activities = []
        for activity_name in activities:
            activity_data = {
                'activity_name': activity_name,
                'feature': feature.id
            }
            serializer = ActivitySerializer(data=activity_data)
            if serializer.is_valid():
                serializer.save()
                created_activities.append(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'feature_id': feature.id,
            'feature_name': feature.feature_name,
            'activities': created_activities
        }, status=status.HTTP_201_CREATED)
    
    def put(self, request):
         # Fetch the activity ID from request data
        activity_id = request.data.get('activity_id')
        if not activity_id:
            return Response({'error': 'ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to get the activity object
        try:
            activity_obj = Activity.objects.get(id=activity_id)
        except Activity.DoesNotExist:
            return Response({'error': 'Activity not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Update the activity data
        serializer = ActivitySerializer(activity_obj, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        activity_id = request.query_params.get('activity_id')
        if not activity_id:
            return Response({'error': 'ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            activity_obj = Activity.objects.get(id=activity_id)
            activity_obj.delete()
            return Response({'error': 'Activity deleted'}, status=status.HTTP_201_CREATED)
        except Activity.DoesNotExist:
            return Response({'error': 'Activity not found'}, status=status.HTTP_404_NOT_FOUND)

class RoleAccessAPIView(APIView):
    def get(self, request):
        user_id = request.query_params.get('user_id')
        company_id = request.query_params.get('company_id')
        role_id = request.query_params.get('role_id')

        # Handle the scenario where company_id, role_id, and user_id are provided
        if company_id and role_id:
            # Fetch feature and activity details associated with the role and company
            role_access_entries = RoleAccess.objects.filter(
                role_id=role_id, company_id=company_id
            ).select_related('feature', 'activity')

            features_dict = {}

            for entry in role_access_entries:
                feature_name = entry.feature.feature_name

                # Initialize the feature in the dictionary if not already present
                if feature_name not in features_dict:
                    features_dict[feature_name] = {}

                # Map activity_name to boolean value based on the activity_status
                features_dict[feature_name][entry.activity.activity_name] = entry.activity_status

            # Flatten the list so it's not nested under individual dictionary entries
            return Response(features_dict, status=status.HTTP_200_OK)

        # If company_id or role_id is not provided, return an error
        return Response({"error": "Company ID and Role ID are required."}, status=status.HTTP_400_BAD_REQUEST)

class UniqueActivityNamesAPIView(APIView):
    def get(self, request):
        # Get all unique activity names from the Activity table
        unique_activity_names = Activity.objects.values_list('activity_name', flat=True).distinct()

        # Convert the result to a list and return it in the response
        return Response(list(unique_activity_names), status=status.HTTP_200_OK)

class RoleListView(APIView):
    permission_classes = [IsValidUser]  # Adjust according to your permissions
    
    def get(self, request):
        try:
            company_id = request.query_params.get('company_id')

            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            # Retrieve all unique roles for the given company
            role_ids = RoleAccess.objects.filter(company__company_id=company_id).values('role').distinct()

            # Fetch the actual Role objects based on the retrieved role IDs
            unique_roles = Role.objects.filter(id__in=[role['role'] for role in role_ids])

            if not unique_roles.exists():
                return Response({"error": "No roles found for the given company."}, status=status.HTTP_404_NOT_FOUND)

            # Serialize the unique roles
            serialized_data = RoleSerializer(unique_roles, many=True).data
            return Response(serialized_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)