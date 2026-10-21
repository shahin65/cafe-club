from django.urls import path

from . import views

urlpatterns = [
    path("deal/<int:scenario_id>/", views.start, name="deal_start"),
    path("deal/<int:scenario_id>/<int:player_count>/", views.choose_mode, name="deal_mode"),
    path(
        "deal/<int:scenario_id>/<int:player_count>/<slug:mode>/",
        views.board,
        name="deal_board",
    ),
    path("deal/card/<int:slot>/", views.card, name="deal_card"),
    path("deal/reveal/<int:slot>/", views.reveal, name="deal_reveal"),
    path("deal/host/", views.host, name="deal_host"),
    path("deal/final/", views.final_board, name="deal_final"),
    path("deal/final/reveal/<int:slot>/", views.final_reveal, name="deal_final_reveal"),
    path("deal/final/<int:slot>/", views.final_card, name="deal_final_card"),
    path("deal/lottery/", views.lottery, name="deal_lottery"),
    path("deal/lottery/reveal/<int:index>/", views.lottery_reveal, name="deal_lottery_reveal"),
    path("deal/lottery/<int:index>/", views.lottery_card, name="deal_lottery_card"),
    path("deal/restart/", views.restart, name="deal_restart"),
    path("deal/cancel/", views.cancel, name="deal_cancel"),
]
