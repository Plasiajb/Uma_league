from django.urls import path
from . import views

urlpatterns = [
    # 新增：网站根目录指向新的 landing_page 视图
    path("", views.landing_page, name="landing"),
    
    # 修改：原主页移动到 /league/ 路径，但 name 保持为 "home" 以便其他链接正常工作
    path("league/", views.home, name="home"),
    
    path("event/<int:event_id>/", views.event_detail, name="event_detail"),
    path("players/", views.players, name="players"),
    path("players/<int:player_id>/", views.player_profile, name="player_profile"),
    path("qualified/", views.qualified, name="qualified"),
    path("payouts/", views.payouts, name="payouts"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me, name="me"),
    path("event/<int:event_id>/enroll/", views.enroll_event, name="enroll_event"),
    path("events/<int:event_id>/report/", views.report_results, name="report_results"),
    path("events/<int:event_id>/round/<int:round_no>/<str:group_name>/room/",
         views.set_room_code, name="set_room_code"),
]