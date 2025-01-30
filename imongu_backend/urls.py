"""imongu_backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse
from rest_framework import routers
from imongu_backend_app import views
from imongu_backend_app.views.auth import *
from imongu_backend_app.views.clone import *
from imongu_backend_app.views.goals import *
from imongu_backend_app.views.password import *
from imongu_backend_app.views.emails import *
from imongu_backend_app.views.employees import *
from imongu_backend_app.views.search import *
from imongu_backend_app.views.insights import *
from imongu_backend_app.views.comments import *
from imongu_backend_app.views.teams import *
from imongu_backend_app.views.ownerParents import *
from imongu_backend_app.views.reports import *
from imongu_backend_app.views.integrations import *
from imongu_backend_app.views.template import *
from imongu_backend_app.views.schedule import *
from imongu_backend_app.views.dashboard import *
from imongu_backend_app.views.role_access import *
from imongu_backend_app.views.ebook import *

router = routers.DefaultRouter()

# router.register(r'imongu/goal-search', GoalDocumentView, basename='goal-search')


def handle_not_found(request, exception=None):
    if request.method is not None:
        return HttpResponse("Hi there👋🏼...little Explorer")


urlpatterns = [
    path("imongu/admin/", admin.site.urls),
    path("imongu/", include("notification.urls")),
    path("imongu/", include("chatbot.urls")),
    path("imongu/", include("payment.urls")),
    path("imongu/integration/", include("integrations.urls"), name="Integrations"),
    path("imongu/api/", include(router.urls)),
    path("imongu/login/", login.as_view(), name="login"),
    path("imongu/signin/", Signup.as_view(), name="signin"),
    path("imongu/profile-edit/", ProfileEdit.as_view(), name="signin"),
    path("imongu/contact/", ContactViews.as_view(), name="contact_us"),
    path("imongu/profile-photo/", ProfileImage.as_view(), name="profile-photo"),
    path(
        "imongu/employee_details/", employee_details.as_view(), name="employee_details"
    ),
    path("imongu/goal/", goal_deatils.as_view(), name="Goal"),
    path("imongu/okr/", okr_details.as_view(), name="Objective"),
    path("imongu/owners/", owners_view.as_view(), name="owners_view"),
    path("imongu/key_results/", key_result.as_view(), name="Key-Results"),
    path("imongu/update-key/", updatekeyresults.as_view(), name="update_key_results"),
    path("imongu/forget-password/", Forgotpassword_mail.as_view(), name="send-email"),
    path(
        "imongu/reset-password/", validatet_forgotpassword.as_view(), name="send-email"
    ),
    path("imongu/send-email/", Sendemail.as_view(), name="Invite-Members"),
    path("imongu/verify_email/", verifyEmail.as_view(), name="verify_email"),
    path("imongu/verify_token/", verifyEmailToken.as_view(), name="verify_token"),
    path("imongu/create-team/", AddUserToTeam.as_view(), name="Teams"),
    path("imongu/comments/", addCoomments.as_view(), name="addCoomments"),
    path("imongu/reaction/", addEmoji.as_view(), name="addEmoji"),
    path("imongu/assignowners/", assignOwners.as_view(), name="assignowners"),
    path("imongu/assignparents/", assignParents.as_view(), name="assignparents"),
    path("imongu/stats/", okr_statistics.as_view(), name="Reports"),
    path("imongu/move-jobs/", moveJobs.as_view(), name="moveJobs"),
    path("imongu/clone-jobs/", cloneJobs.as_view(), name="cloneJobs"),
    path("imongu/insights/", insights.as_view(), name="insights"),
    path(
        "imongu/insights/stategic-report/",
        stategicReport.as_view(),
        name="stategicReport",
    ),
    path(
        "imongu/search/<str:query>/", SearchDocuments.as_view(), name="SearchDocument"
    ),
    path("imongu/connector/", SaveJiraCredentials.as_view(), name="Integrations"),
    path("imongu/jira/webhook/", JiraWebhookView.as_view(), name="JiraWebhookView"),
    path("imongu/shared-okr/", sharedOkr.as_view(), name="sharedOkr"),
    # path("testing", Testing.as_view(), name="testing"),
    path("", lambda request: HttpResponse("YAYY!! iMongu's BACKEND IS LIVE")),
    path("imongu/template/", TemplateView.as_view(), name="Templates"),
    path("imongu/template-get/", TemplateGetView.as_view(), name="template-get"),
    path("imongu/template-answer/", UserAnswerView.as_view(), name="template-answer"),
    path("imongu/schedule/", ScheduleView.as_view(), name="Schedules"),
    path("imongu/goal-user/", GoalUserAPIView.as_view(), name="goal-user"),
    path(
        "imongu/userschedule-get/",
        UserScheduleGetView.as_view(),
        name="userschedule-get",
    ),
    path(
        "imongu/participationschedule-get/",
        ParticipationScheduleGetView.as_view(),
        name="participationschedule-get",
    ),
    path(
        "imongu/template-comments/",
        TempCommentsView.as_view(),
        name="template-comments",
    ),
    path("imongu/template-view/", FetchTemplatesView.as_view(), name="template-view"),
    path("imongu/okrs/", OKRListView.as_view(), name="okr-list"),
    path(
        "imongu/admin-touchbase/",
        AdminGoalDetailsView.as_view(),
        name="admin-touchbase",
    ),
    path("imongu/role/", RoleAPIView.as_view(), name="role"),
    path("imongu/feature/", FeatureAPIView.as_view(), name="feature"),
    path("imongu/activity/", ActivityAPIView.as_view(), name="activity"),
    path("imongu/team-colab/", TeamColabView.as_view(), name="Team-Collabs"),
    path("imongu/role-access/", RoleAccessAPIView.as_view(), name="role-access"),
    path(
        "imongu/activity-list/",
        UniqueActivityNamesAPIView.as_view(),
        name="activity-list",
    ),
    path("imongu/logout/", LogoutView.as_view(), name="logout"),
    path("imongu/quarter/", QuarterAPiView.as_view(), name="quarter"),
    path("imongu/hierarchy/", EmployeeHierarchyView.as_view(), name="hierarchy"),
    path("imongu/role-list/", RoleListView.as_view(), name="role-list"),
    path("imongu/report-to/", HigherLevelEmployeeAPIView.as_view(), name="report-to"),
    path('imongu/generate-report/', GenerateReportView.as_view(), name='generate-report'),
    path('imongu/reactive/', ReactivateAccountAPI.as_view(), name='reactive'),
    path('imongu/ebook-contact/', ContactCreateView.as_view(), name='ebook-contact'),
    path('imongu/delete-item/', DeletedItemsView.as_view(), name='delete-item'),
]
