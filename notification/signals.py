from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from imongu_backend_app.models import key_results
from imongu_backend_app.Serializers import userserializers
import json
from notification.Serializers import NotificationSerializers
from notification.models import Notifications , UserNotification
from imongu_backend_app.models import Room
from datetime import timedelta,datetime
from notification.tasks import send_deadline_reminder 
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJob
import logging
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")
scheduler.start()

@receiver(post_save, sender=Notifications)
def notification_created(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        company_id = instance.company_id.company_id

        notification_data = {}
        serializer = NotificationSerializers(instance)
        notification_data = serializer.data
        user_data = userserializers(instance.user_id)
        notification_data.update(user_data.data)
        notification_data['is_seen']=False
        async_to_sync(channel_layer.group_send)(
            company_id,
            {
                "type": "send_notification",
                "message": json.dumps(notification_data)
            }
        )

@receiver(post_save, sender=key_results)
def schedule_deadline_reminder(sender, instance, created, **kwargs):
    # Schedule a task to send a reminder 2 days before the deadline
    if instance.deadline and created:
        print("deadline =", instance.deadline)

        # Initialize deadline_date as None
        deadline_date = None

        # Check if the deadline is a string
        if isinstance(instance.deadline, str):
            # Attempt to parse the string with different formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # Format with microseconds
                "%Y-%m-%dT%H:%M:%SZ",      # Format without microseconds
                "%Y-%m-%dT%H:%M:%S",       # Standard format without timezone
                "%Y-%m-%d",                 # Just the date
            ]

            # Try parsing with each format until one works
            for fmt in formats:
                try:
                    deadline_date = datetime.strptime(instance.deadline, fmt)
                    break  # Exit loop if parsing is successful
                except ValueError:
                    continue  # Try the next format

        # If the deadline is already a datetime object, assign it directly
        if isinstance(instance.deadline, datetime):
            deadline_date = instance.deadline

        # If we still don't have a valid deadline_date, handle the error as needed
        if not deadline_date:
            print("Could not parse deadline:", instance.deadline)
            return  # Or raise an error, or log this appropriately

        # Get the current time
        current_time = datetime.now().time()

        # Calculate reminder time: 2 days before the deadline
        reminder_time = datetime.combine(deadline_date.date(), current_time) - timedelta(days=2)

        # Ensure the key_id is unique for each task
        key_id = instance.key_id

        # Schedule the reminder task
        task = scheduler.add_job(
            send_deadline_reminder,
            args=[key_id],
            next_run_time=reminder_time,
            id=key_id
        )

        
@receiver(post_delete, sender=key_results)
def stop_scheduler(sender, instance, **kwargs):
    try:
        key_id = instance.key_id
        scheduler.remove_job(key_id)
        logger.info(f"Scheduler stopped for key_result_id: {key_id}")
    except Exception as e:
        logger.error(f"Error stopping scheduler for key_result_id: {instance.key_id}, Error: {e}")        


@receiver(post_delete, sender=UserNotification)
def delete_notification_if_no_user_notifications(sender, instance, **kwargs):
    try:
        notification = instance.notify_id
        if notification:
            if not UserNotification.objects.filter(notify_id=notification).exists():
                notification.delete()
    except UserNotification.DoesNotExist:
        pass
    except Exception as e:
        print(f"An error occurred: {str(e)}")
