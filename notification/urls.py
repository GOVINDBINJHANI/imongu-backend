from django.urls import path
from . import views

urlpatterns = [
    # path('', views.index, name='index'),
    path('notification/',views.notificationViews.as_view(),name='notify'),
]