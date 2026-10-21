from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("nights/", views.page, {"page": "nights"}, name="nights"),
    path("games/", views.page, {"page": "games"}, name="games"),
    path("tables/", views.page, {"page": "tables"}, name="tables"),
]
