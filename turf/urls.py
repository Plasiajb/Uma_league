
from django.urls import path
from . import views
urlpatterns = [
    path("", views.home, name="home"),
    path("event/<int:event_id>/", views.event_detail, name="event_detail"),
    path("players/", views.players, name="players"),
    path("qualified/", views.qualified, name="qualified"),
    path("payouts/", views.payouts, name="payouts"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me, name="me"),
    path("event/<int:event_id>/enroll/", views.enroll_event, name="enroll_event"),
    path("events/<int:event_id>/report/", views.report_results, name="report_results"),
    path("events/<int:event_id>/round/<int:round_no>/<str:group_name>/room/", views.set_room_code, name="set_room_code"),
    path("players/<int:player_id>/", views.player_profile, name="player_profile"),

]
