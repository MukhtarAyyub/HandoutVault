"""
exams.urls — mounted at /exam-prep/ (see config/urls.py).

    /exam-prep/                          hub (login required)
    /exam-prep/<kind>/                   browse + filter     kind = past-questions | summaries
    /exam-prep/<kind>/add/               Admin: create
    /exam-prep/<kind>/<id>/              detail + preview
    /exam-prep/<kind>/<id>/download/     counts the download, streams the file
    /exam-prep/<kind>/<id>/edit/         Admin: update
    /exam-prep/<kind>/<id>/delete/       Admin: confirm (GET) then delete (POST)

`add/` is listed before `<int:pk>/` for readability only — the int converter
can't match the word "add".
"""
from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("", views.hub, name="hub"),
    path("<slug:kind>/", views.resource_list, name="list"),
    path("<slug:kind>/add/", views.resource_add, name="add"),
    path("<slug:kind>/<int:pk>/", views.resource_detail, name="detail"),
    path("<slug:kind>/<int:pk>/download/", views.resource_download, name="download"),
    path("<slug:kind>/<int:pk>/edit/", views.resource_edit, name="edit"),
    path("<slug:kind>/<int:pk>/delete/", views.resource_delete, name="delete"),
]
