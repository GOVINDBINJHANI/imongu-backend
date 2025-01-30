from django.db import models
from imongu_backend_app.models import company,User
from django.utils import timezone

# Create your models here.
class Notifications(models.Model):
    notify_id=models.CharField(primary_key=True,max_length=255)
    company_id=models.ForeignKey(company, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User,on_delete=models.CASCADE)
    notification=models.TextField(max_length=255)
    date_created = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=255, default='')
    title = models.CharField(max_length=255, default='')
    changes = models.JSONField(default=dict,blank=True)
    isDeleted = models.BooleanField(default=True)

class UserNotification(models.Model):
    notify_id=models.ForeignKey(Notifications,on_delete=models.CASCADE)
    user_id = models.ForeignKey(User,on_delete=models.CASCADE)
    is_seen=models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone.now)
