from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("hisobot/", views.index, name="index"),
    path("hisobot/<int:period_id>/", views.progress, name="progress"),
    path("hisobot/<int:period_id>/excel/", views.download_report, name="download_report"),
    path("hisobot/<int:period_id>/fayllar/", views.download_files, name="download_files"),
]
