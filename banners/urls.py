from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import ads_views, auth_views, places_views, profile_views, pwa_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("install/", pwa_views.install_page, name="install_app"),
    path("settings/", views.app_settings, name="app_settings"),
    path("privacy/", views.legal_page, {"key": "privacy"}, name="privacy"),
    path("terms/", views.legal_page, {"key": "terms"}, name="terms"),
    path("account/login/", LoginView.as_view(template_name="account/login.html", redirect_authenticated_user=True), name="login"),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path("account/register/", auth_views.register, name="register"),
    path("account/username/", auth_views.save_username, name="save_username"),
    path("account/profile/", profile_views.profile_page, name="profile"),
    path("account/gmail/send/", profile_views.send_gmail_code, name="gmail_send"),
    path("account/gmail/verify/", profile_views.verify_gmail_code, name="gmail_verify"),
    path("account/profile/details/", profile_views.save_profile_details, name="profile_details"),
    path("account/profile/blue-tick/", profile_views.request_blue_tick, name="request_blue_tick"),
    path("nights/", views.page, {"page": "nights"}, name="nights"),
    path("games/", views.page, {"page": "games"}, name="games"),
    path("tables/", views.page, {"page": "tables"}, name="tables"),
    path("ads/", ads_views.ads_page, name="ads"),
    path("ads/create/", ads_views.create_ad, name="ad_create"),
    path("ads/<int:ad_id>/", ads_views.ad_detail, name="ad_detail"),
    path("ads/<int:ad_id>/like/", ads_views.like_ad, name="ad_like"),
    path("location/", places_views.places, name="location"),
    path("location/submit/", places_views.submit_venue, name="venue_submit"),
    path("location/<int:venue_id>/", places_views.venue_detail, name="venue_detail"),
    path("location/<int:venue_id>/rate/", places_views.rate_venue, name="venue_rate"),
    path("location/<int:venue_id>/comment/", places_views.comment_venue, name="venue_comment"),
]
