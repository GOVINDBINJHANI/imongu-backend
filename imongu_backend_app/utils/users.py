from imongu_backend_app.models import User,employee,Room
from imongu_backend_app.Serializers import userserializers,employeeserializers
from payment.utils import *
from django.db.models import Case, Value, When

def get_verified_user_details(user):
    user=userserializers(user)
    user_id=user.data.get('user_id')
    email=user.data.get('email')
    super_admin_role = Role.objects.filter(role_name='Admin').values('id').first()

    employees = employee.objects.filter(user_id=user_id)
    # Define a custom ordering using Django's Case and When
    employees = employees.annotate(
        is_manager=Case(
            When(role=super_admin_role['id'], then=Value(1)),
            default=Value(0),
        )
    )
    Employee = employees.order_by("-is_manager")

    username = user.data.get('username')
    # company_obj=company.objects.filter(user_id=user_id).first()
    updated_serializer_data={}
    profile_image = user.data.get('profile_image')
    updated_serializer_data['profile_image'] = profile_image
    updated_serializer_data['username'] = username
    # updated_serializer_data['company_name'] = company_obj.company_name
    serializer = employeeserializers(Employee, many=True)
    data = serializer.data
    for emp in data:
        com_id = emp.get('company_id')
        manger = employee.objects.filter(company_id=com_id,role=super_admin_role['id']).first()
        room, created = Room.objects.get_or_create(user_id=manger.user_id, company_id=manger.company_id)
        emp['profile_image'] = manger.user_id.profile_image
        emp['username'] = manger.user_id.username
        emp['email'] = manger.user_id.email
        emp['company_name'] = manger.company_id.company_name
        emp['room_id'] = room.room_id

    # user_subcription = get_plan_data(user_id)
    # updated_serializer_data['plan_name'] = user_subcription['plan_name']
    # updated_serializer_data["expiry_date"] = user_subcription["current_period_end"]
    # updated_serializer_data["creation_date"] = user_subcription["current_period_start"]
    updated_serializer_data['email'] = email
    updated_serializer_data['employees'] = data
    return updated_serializer_data

def get_user_details(all_people):
    user_list = []
    for user in all_people:
        user_id = user['user_id']       
        user_obj = User.objects.get(user_id = user_id)
        user_list.append({"user_id" : user_id , "username" : user_obj.username , "email" : user_obj.email})
    return user_list
