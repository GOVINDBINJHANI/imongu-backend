from imongu_backend_app.models import User, company
from django.db import models
from django.utils import timezone
import requests
from datetime import timedelta


class GoogleToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.CharField(max_length=255)
    expiry = models.CharField(max_length=500, null=False)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "google_token"

    def __str__(self):
        return f"Google Token for {self.user.username}"


class TrelloConnection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(company, on_delete=models.CASCADE)
    connection_name = models.CharField(max_length=100)  
    api_key = models.CharField(max_length=255)
    token = models.CharField(max_length=255)
    board_id = models.CharField(max_length=255, null=True, blank=True)  
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "trello"

    def __str__(self):
        return f"trello Token for {self.user.username}"

class AsanaConnection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    connection_name = models.CharField(max_length=100, null=True, blank=True)
    company = models.ForeignKey(company, on_delete=models.CASCADE)
    access_token = models.TextField()
    
    class Meta:
        db_table = "asana_connection"  


class MicrosoftToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expiry = models.DateTimeField()
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "microsoft_token"

    def __str__(self):
        return f"Microsoft Token for {self.user.username}"
