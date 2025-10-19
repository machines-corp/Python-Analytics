from django.contrib import admin
from django.urls import path
from empleos.views import JobSearchView, ChatStart, ChatMessage, TaxonomyView, JobDetailsView, JobPostingListCreateAPI, JobPostingChoicesAPI

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/search", JobSearchView.as_view(), name="job-search"),
    path("api/chat/start", ChatStart.as_view()),
    path("api/chat/<int:conversation_id>/message", ChatMessage.as_view()),
    path("api/taxonomy", TaxonomyView.as_view(), name="taxonomy"),
    path("api/job/<int:job_id>", JobDetailsView.as_view(), name="job-details"),
    path("api/jobpostings/", JobPostingListCreateAPI.as_view(), name="jobposting-list-create"),
    path("api/jobpostings/choices", JobPostingChoicesAPI.as_view(), name="jobposting-choices"),
]