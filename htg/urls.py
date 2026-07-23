from django.urls import path
from . import views

app_name = 'htg'

urlpatterns = [
    path('', views.home, name='home'),
]