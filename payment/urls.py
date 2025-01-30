from django.urls import path
from .views import StripeWebhookView, CustomerPortal, SubscriptionView

urlpatterns = [
    # path('', views.index, name='index'),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path(
        "create-customer-portal-session/",
        CustomerPortal.as_view(),
        name="customer_portal",
    ),
    path("subscription/", SubscriptionView.as_view(), name="subscription"),
]
