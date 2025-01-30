from django.apps import AppConfig


class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notification'

    # 1. 👇 Add this line for signals
    def ready(self):
        import notification.signals