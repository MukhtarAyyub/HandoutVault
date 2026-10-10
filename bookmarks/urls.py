"""
bookmarks.urls — mounted at /bookmarks/ (see config/urls.py).

    /bookmarks/             the current student's saved materials
    /bookmarks/toggle/<id>/ POST-only add/remove (bookmarks.views.toggle_bookmark)
"""
from django.urls import path

from . import views

app_name = "bookmarks"

urlpatterns = [
    path("", views.bookmark_list, name="bookmark_list"),
    path("toggle/<int:pk>/", views.toggle_bookmark, name="toggle_bookmark"),
]
