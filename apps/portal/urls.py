from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/", views.profile, name="profile"),
    path("<slug:slug>/", views.generic_list, name="list"),
    path("<slug:slug>/add/", views.generic_form, name="add"),
    path("<slug:slug>/<int:pk>/edit/", views.generic_form, name="edit"),
    path("<slug:slug>/<int:pk>/delete/", views.generic_delete, name="delete"),
]
