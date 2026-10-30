from django.urls import path

from assistant import views

urlpatterns = [
    path("", views.home, name="assistant_home"),
    path("settings/", views.settings_page, name="assistant_settings"),
    path("reports/", views.reports, name="assistant_reports"),
    path("review/", views.manager_queue, name="assistant_manager"),
    path("case/<int:pk>/", views.case_detail, name="assistant_case"),
    path("<slug:scope>/criteria/", views.policy_edit, name="assistant_policy"),
    path("<slug:scope>/", views.queue, name="assistant_queue"),
]
