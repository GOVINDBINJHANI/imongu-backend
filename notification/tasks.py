# tasks.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from imongu_backend_app.models import key_results
import logging
from imongu_backend_app.utils.notification import save_notification

logger = logging.getLogger(__name__)

def send_deadline_reminder(key_result_id):
    try:
        # Fetch the key_result instance
        key_result = key_results.objects.get(key_id=key_result_id)
        # Send notification or perform any other reminder action
        company_obj = key_result.okr_id.goal_id.company_id
        company_id = company_obj.company_id
        user = company_obj.user_id
        changes = {
            'key_id': key_result.key_id,
        }
        message = f"Reminder: The deadline for {key_result.title} is approaching on {key_result.deadline.strftime('%Y-%m-%d %H:%M:%S')}."
        save_notification(company_id, message,user,"reminder" , "Reminder", changes)
    except Exception as e:
        logger.error(f"Error in send_deadline_reminder: {e}")
        raise e

