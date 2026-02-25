from django.urls import path
from .views import ActivateLicenseView

urlpatterns = [
    path('activate/', ActivateLicenseView.as_view()),
]