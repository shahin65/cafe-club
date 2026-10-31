from django.urls import path

from assistant import views

urlpatterns = [
    path("", views.home, name="assistant_home"),
    path("settings/", views.settings_page, name="assistant_settings"),
    path("content/", views.content_home, name="assistant_content"),
    path("content/scenarios/", views.content_scenarios, name="assistant_content_scenarios"),
    path("content/scenarios/<int:pk>/", views.content_scenario, name="assistant_content_scenario"),
    path("reports/", views.reports, name="assistant_reports"),
    path("review/", views.manager_queue, name="assistant_manager"),
    path("case/<int:pk>/", views.case_detail, name="assistant_case"),
    path("<slug:scope>/criteria/", views.policy_edit, name="assistant_policy"),
    path("<slug:scope>/", views.queue, name="assistant_queue"),
]
