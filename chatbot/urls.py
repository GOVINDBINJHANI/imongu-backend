from django.urls import path
from . import views

urlpatterns = [
    # path('', views.index, name='index'),
    path("messenger/", views.ChatbotViews.as_view(),name="Chatbot"),
    path("chat-message/", views.QueryLLMView.as_view(),name="Chat-Conversation"),

]