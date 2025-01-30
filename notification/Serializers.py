from rest_framework import serializers
from .models import Notifications,UserNotification

class NotificationSerializers(serializers.ModelSerializer):
    class Meta:
        model=Notifications
        fields='__all__'

class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model=UserNotification
        fields='__all__'