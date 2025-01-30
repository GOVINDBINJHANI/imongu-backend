from django.urls import path
from .views.schedule_meet import AuthorizeGoogleCalendar, GoogleCalendar
from .views.trellowebhook import SaveTrelloCredentials, TrelloWebhookView
from .views.asana import AsanaConnectionView, AsanaWebhookView
from .views.outlook import MicrosoftCalendar

urlpatterns = [
    path("auth-calendar", AuthorizeGoogleCalendar.as_view(), name="auth-calendar"),
    path("google-calendar", GoogleCalendar.as_view(), name="Chatbot"),
    path('save_credentials/', SaveTrelloCredentials.as_view(), name="Integrations"),
    path('trello/webhook/', TrelloWebhookView.as_view(), name='trello_webhook'),
    path('asana/connection/', AsanaConnectionView.as_view(), name='asana-connection'),
    path('asana/webhook/', AsanaWebhookView.as_view(), name='asana-webhook'),

    path('outlook/', MicrosoftCalendar.as_view(), name='outlook'),
]
