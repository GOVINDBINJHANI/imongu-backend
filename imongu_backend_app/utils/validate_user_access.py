from rest_framework.exceptions import NotFound, PermissionDenied
from imongu_backend_app.models import company, employee, Feature, Activity, RoleAccess


def validate_user_company_access(user_id, company_id):
    """
    Validate that the company exists and the user has access to it.
    
    Args:
        user_id (int): The ID of the user.
        company_id (str): The ID of the company.
    
    Raises:
        NotFound: If the company does not exist.
        PermissionDenied: If the user does not have access to the company.
    """
    try:
        company_obj = company.objects.get(company_id=company_id)
        # Check if the user is an employee of the company and fetch the role
        employee_obj = employee.objects.get(user_id=user_id, company_id=company_obj)  
        # If employee exists, return the role ID
        return employee_obj.role.pk
    except company.DoesNotExist:
        raise NotFound("Company not found") 
    except employee.DoesNotExist:
        raise PermissionDenied("User does not have access to this company")
    
def validate_feature_activity_access(role_id, company_id, feature_name, activity_name):
    """
    Validate if the user has access to a specific feature and activity in the company.
    
    Args:
        role_id (int): The ID of the role of the user.
        company_id (int): The ID of the company.
        feature_name (str): The name of the feature to check access for.
        activity_name (str): The name of the activity to check access for.
    
    Raises:
        PermissionDenied: If the user does not have access to the feature or activity.
    """
    try:
        # Get the feature by its name
        feature_obj = Feature.objects.get(feature_name=feature_name)

        # Get the activity under the given feature
        activity_obj = Activity.objects.get(activity_name=activity_name, feature=feature_obj)

        # Fetch RoleAccess for the role, feature, activity, and company
        role_access = RoleAccess.objects.filter(
            role_id=role_id,
            feature=feature_obj,
            activity=activity_obj,
            company_id=company_id
        ).first()

        # If no RoleAccess exists or activity_status is False, deny access
        if not role_access or not role_access.activity_status:
            raise PermissionDenied(f"User does not have access to the activity '{activity_name}' in feature '{feature_name}'.")

    except Feature.DoesNotExist:
        raise NotFound(f"Feature '{feature_name}' not found.")
    except Activity.DoesNotExist:
        raise NotFound(f"Activity '{activity_name}' not found.")


def employee_feature_activity_access(role_id, company_id, feature_name, activity_name):
    try:
        feature_obj = Feature.objects.get(feature_name=feature_name)
        activity_obj = Activity.objects.get(activity_name=activity_name, feature=feature_obj)
        role_access = RoleAccess.objects.filter(
            role_id=role_id,
            feature=feature_obj,
            activity=activity_obj,
            company_id=company_id
        ).first()

        return bool(role_access and role_access.activity_status)

    except (Feature.DoesNotExist, Activity.DoesNotExist):
        # Return False if the feature or activity doesn't exist
        return False

def get_all_reportees(employee_obj):
        reportees = set()
        stack = [employee_obj]

        while stack:
            current_employee = stack.pop()
            reportees.add(current_employee.employee_id)
            subordinates = employee.objects.filter(report_to=current_employee)
            stack.extend(subordinates)

        return reportees