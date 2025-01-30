from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from google.auth.transport import requests
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from notification.models import UserNotification, Notifications
from imongu_backend_app.Serializers import userserializers
from notification.Serializers import NotificationSerializers,UserNotificationSerializer
from imongu_backend_app.models import User,company
from django.shortcuts import get_object_or_404
from django.db.models import Q
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId

class CustomPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class notificationViews(GenericAPIView):
    permission_classes = [IsValidUser]


    def put(self, request):
        user_id = GetUserId.get_user_id(request)
        notify_id = request.data.get('notify_id')

        try:
            notification = UserNotification.objects.get(notify_id=notify_id, user_id=user_id)
        except UserNotification.DoesNotExist:
            return Response({"detail": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

        if not notification.is_seen:
            notification.is_seen = True
            notification.save()

        serializer = UserNotificationSerializer(notification)
        serialized_data = serializer.data

        return Response(serialized_data, status=status.HTTP_200_OK)
    
    def get(self,request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')
        all_notifications = UserNotification.objects.filter(user_id=user_id, notify_id__company_id=company_id).order_by('-date_created')

        unseen_count = all_notifications.filter(is_seen=False).count()

        data = []
        for notification in all_notifications:
            notification_data = {}
            notification_obj = notification.notify_id
            serializer = NotificationSerializers(notification_obj)
            user_data = userserializers(notification_obj.user_id)
            notification_data = serializer.data
            user_notification_data = UserNotificationSerializer(notification)
            notification_data.update(user_data.data)
            notification_data.update(user_notification_data.data)
            data.append(notification_data)

        response_data = {
            'unseen_count': unseen_count,
            'notifications': data
        }

        return Response(response_data)
    
    def delete(self,request):
        user_notification_id = request.query_params.get('id')
        company_id = request.query_params.get('company_id','')
        user_id = GetUserId.get_user_id(request)
        try:
            if user_notification_id:
                user_notification = get_object_or_404(UserNotification, pk=user_notification_id).delete()

            if company_id and user_id:
                UserNotification.objects.filter(Q(user_id=user_id) & Q(notify_id__company_id=company_id)).delete()
                
            return Response({'message': 'Notification deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=400)