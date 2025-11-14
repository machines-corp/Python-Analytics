from django.contrib import admin
from django.urls import path, include
from empleos.views import JobSearchView, ChatStart, ChatMessage, TaxonomyView, JobDetailsView, JobPostingListCreateAPI, JobPostingChoicesAPI
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/search", JobSearchView.as_view(), name="job-search"),
    path("api/chat/start", ChatStart.as_view()),
    path("api/chat/<int:conversation_id>/message", ChatMessage.as_view()),
    path("api/taxonomy", TaxonomyView.as_view(), name="taxonomy"),
    path("api/job/<int:job_id>", JobDetailsView.as_view(), name="job-details"),
    path("api/jobpostings/", JobPostingListCreateAPI.as_view(), name="jobposting-list-create"),
    path("api/jobpostings/choices", JobPostingChoicesAPI.as_view(), name="jobposting-choices"),
    path('api/auth/', include('usuarios.urls')),
        # Endpoints JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]