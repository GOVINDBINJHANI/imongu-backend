from django.db import models
from imongu_backend_app.models import User, company
from django.utils import timezone


# Create your models here.
class Subscription(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    company_id = models.OneToOneField(company, on_delete=models.CASCADE)
    plan_name = models.CharField(max_length=255)
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    subscription_stripe_id = models.CharField(max_length=255, null=True, blank=True)
    customer_stripe_id = models.CharField(max_length=255)
    stripe_product_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255)
    amount = models.IntegerField(default=0)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True)
    free_trial_status = models.BooleanField(default=True)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "subscription"
