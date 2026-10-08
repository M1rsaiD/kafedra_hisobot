from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("periods/<int:period_id>/download/", views.download_report, name="download_report"),
]
