from django.contrib import admin
from django.urls import path
from empleos.views import JobSearchView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/search", JobSearchView.as_view(), name="job-search"),
]