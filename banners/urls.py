from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import auth_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("account/login/", LoginView.as_view(template_name="account/login.html", redirect_authenticated_user=True), name="login"),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path("account/register/", auth_views.register, name="register"),
    path("account/username/", auth_views.save_username, name="save_username"),
    path("nights/", views.page, {"page": "nights"}, name="nights"),
    path("games/", views.page, {"page": "games"}, name="games"),
    path("tables/", views.page, {"page": "tables"}, name="tables"),
    path("ads/", views.page, {"page": "ads"}, name="ads"),
    path("location/", views.page, {"page": "location"}, name="location"),
]
