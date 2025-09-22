from django.contrib import admin
from django.urls import path
from empleos.views import JobSearchView, ChatStart, ChatMessage

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/search", JobSearchView.as_view(), name="job-search"),
    path("api/chat/start", ChatStart.as_view()),
    path("api/chat/<int:conversation_id>/message", ChatMessage.as_view()),
]