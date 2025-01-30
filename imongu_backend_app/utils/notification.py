from imongu_backend_app.models import User,company,employee
import uuid, json
from notification.models import Notifications,UserNotification
from imongu_backend_app.utils.owners import *

def save_notification(company_id , message, user, type, title, changes, isDeleted=False):
    notify_id = str(uuid.uuid4())
    company_obj = company.objects.get(company_id=company_id)
    notification_obj = Notifications.objects.create(
        notify_id=notify_id,
        company_id = company_obj ,
        notification = message,
        user_id = user,
        type=type,
        title=title ,
        changes=changes,
        isDeleted=isDeleted
        )
    company_users = employee.objects.filter(company_id=company_obj).values_list('user_id',flat=True)
    user_objs = User.objects.filter(user_id__in=company_users)
    user_notifications = [ UserNotification(notify_id=notification_obj, user_id=user_obj) for user_obj in user_objs ]
    # Bulk insert UserNotification objects
    UserNotification.objects.bulk_create(user_notifications)
