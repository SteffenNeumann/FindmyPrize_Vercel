from django.urls import path
from . import views

urlpatterns = [
    path('', views.run_scraper, name='run_scraper'),
]
