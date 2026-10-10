from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from materials.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("catalog/", include("academics.urls", namespace="academics")),
    path("materials/", include("materials.urls", namespace="materials")),
    path("bookmarks/", include("bookmarks.urls", namespace="bookmarks")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
