"""
materials.urls — mounted at /materials/ (see config/urls.py).

    /materials/                browse/search/filter (material_list)
    /materials/upload/         Admin: create (material_upload)
    /materials/dashboard/      Admin: stats + recent activity
    /materials/<id>/           detail + preview (material_detail)
    /materials/<id>/download/  @login_required, logs + streams the file
    /materials/<id>/edit/      Admin: update
    /materials/<id>/delete/    Admin: confirm (GET) then delete (POST)

"upload/" and "dashboard/" are listed before "<int:pk>/" purely for
readability — Django's `<int:pk>` converter only ever matches digits, so
it can't actually shadow either literal path regardless of order.
"""
from django.urls import path

from . import views

app_name = "materials"

urlpatterns = [
    path("", views.material_list, name="material_list"),
    path("upload/", views.material_upload, name="material_upload"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("<int:pk>/", views.material_detail, name="material_detail"),
    path("<int:pk>/download/", views.material_download, name="material_download"),
    path("<int:pk>/edit/", views.material_edit, name="material_edit"),
    path("<int:pk>/delete/", views.material_delete, name="material_delete"),
]
