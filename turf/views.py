from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count
from django.db.models.functions import Lower
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .models import (
    Season, Stage, Event, Group, Heat, Result, Standing, Payout,
    Player, Enrollment, GroupMembership, PublishedRank, SelfReport
)

# +++ 新增的视图函数 +++
def landing_page(request):
    """
    渲染独立的入口/登陆页面。
    """
    return render(request, "guest/landing.html")
# +++ 新增结束 +++


def current_stage():
    return Stage.objects.order_by('-id').first()

def home(request):
    stage = current_stage()
    events = Event.objects.filter(stage=stage) if stage else []
    ctx = {"stage": stage, "events": events}
    return render(request, "guest/home.html", ctx)

def event_detail(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)
    standings = Standing.objects.filter(event=event).order_by('rank')
    heats = Heat.objects.filter(event=event).order_by('round_no','group__name')
    results = Result.objects.filter(heat__in=heats, is_npc=False).select_related('player','heat','heat__group').order_by('heat__round_no', 'heat__group__name', 'place')
    gms = GroupMembership.objects.filter(event=event).order_by('round_no','group__name','player__name')
    published = PublishedRank.objects.filter(event=event).order_by('rank')
    can_report = False
    if request.user.is_authenticated:
        player = getattr(request.user, "player", None) or Player.objects.filter(user=request.user).first()
        if player and GroupMembership.objects.filter(event=event, player=player).exists():
            can_report = True
    ctx = {
        "event": event, "standings": standings, "heats": heats, "results": results,
        "group_members": gms, "published": published, "can_report": can_report,
    }
    return render(request, "guest/event_detail.html", ctx)

# ===================== 选手列表 =====================
def players(request):
    payout_map = {
        r['player_id']: (r['total'] or 0)
        for r in Payout.objects.values('player_id').annotate(total=Sum('total_amount'))
    }
    events_map = {
        r['player_id']: r['ev']
        for r in Standing.objects.values('player_id').annotate(ev=Count('event', distinct=True))
    }
    rows = []
    for p in Player.objects.all().order_by('name'):
        rows.append({
            "id": p.id, "name": p.name, "total": payout_map.get(p.id, 0),
            "events": events_map.get(p.id, 0), "honors": p.honors_dict(),
        })
    rows.sort(key=lambda x: (-x["total"], x["name"]))
    return render(request, "guest/players.html", {"rows": rows})

def qualified(request):
    settlements = Event.objects.filter(format="settlement").order_by('id')
    finals = Event.objects.filter(format="final").order_by('id')
    return render(request, "guest/qualified.html", {"settlements": settlements, "finals": finals})

def payouts(request):
    ps = Payout.objects.select_related('event','player').order_by('-event__id','-total_amount')
    return render(request, "guest/payouts.html", {"payouts": ps})

def signup(request):
    if request.method=="POST":
        u = request.POST.get("username"); p = request.POST.get("password"); n = request.POST.get("display_name")
        if not (u and p and n):
            messages.error(request,"必填项为空")
            return render(request,"guest/signup.html")
        if User.objects.filter(username=u).exists():
            messages.error(request,"用户名已存在")
            return render(request,"guest/signup.html")
        user = User.objects.create_user(u, password=p)
        Player.objects.create(user=user, name=n)
        login(request, user)
        return redirect("me")
    return render(request,"guest/signup.html")

def login_view(request):
    if request.method=="POST":
        u = request.POST.get("username"); p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            return redirect("home")
        messages.error(request,"用户名或密码错误")
    return render(request,"guest/login.html")

def logout_view(request):
    logout(request)
    return redirect("home")

@login_required
def me(request):
    player = Player.objects.filter(user=request.user).first()
    if player:
        return redirect("player_profile", player_id=player.id)
    if request.method == "POST":
        pass
    messages.info(request, "当前账号未绑定选手名，请先创建后再进入个人主页。")
    return render(request, "guest/me.html", {"player": None})

@login_required
def enroll_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    player = getattr(request.user, "player", None) or Player.objects.filter(user=request.user).first()
    if not player:
        messages.error(request,"请先注册选手名")
        return redirect("signup")
    Enrollment.objects.get_or_create(event=event, player=player, defaults={"status":"active"})
    messages.success(request,"报名成功")
    return redirect("event_detail", event_id=event.id)

# ---------------------------
# 战绩自助填报
# ---------------------------
def _per_round_horses(event: Event) -> int:
    return 2 if event.format in ("settlement", "final") else 1
@login_required
def report_results(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)
    player = Player.objects.filter(user=request.user).first()
    if not player:
        messages.error(request, "当前账号还没有选手名，请先在『我的』页面创建。")
        return redirect("me")
    memberships = list(GroupMembership.objects.filter(event=event, player=player).order_by("round_no"))
    if not memberships:
        messages.error(request, "你未参与本赛事或尚未分组。")
        return redirect("event_detail", event_id=event.id)
    horses = _per_round_horses(event)
    prefill = {}
    for sr in SelfReport.objects.filter(event=event, player=player, verified=False):
        prefill[f"r{sr.round_no}_h{sr.horse_index}"] = sr.place
    if request.method == "POST":
        updates = 0
        for m in memberships:
            for h in range(1, horses + 1):
                key = f"r{m.round_no}_h{h}"
                val = request.POST.get(key, "").strip()
                if not val:
                    continue
                try:
                    place = int(val)
                except ValueError:
                    messages.error(request, f"第{m.round_no}轮 第{h}匹：请输入1-12的整数。")
                    return redirect("report_results", event_id=event.id)
                if not (1 <= place <= 12):
                    messages.error(request, f"第{m.round_no}轮 第{h}匹：名次必须在1-12之间。")
                    return redirect("report_results", event_id=event.id)
                SelfReport.objects.update_or_create(
                    event=event, player=player, round_no=m.round_no, horse_index=h,
                    defaults={"place": place, "verified": False}
                )
                updates += 1
        messages.success(request, f"已提交 {updates} 条名次，等待裁判审核。") if updates else messages.info(request, "没有任何更新。")
        return redirect("event_detail", event_id=event.id)
    return render(request, "turf/report_results.html", {
        "event": event, "memberships": memberships,
        "horses": horses, "prefill": prefill,
    })

# ---------------------------
# 房主上传房号
# ---------------------------
@login_required
def set_room_code(request, event_id: int, round_no: int, group_name: str):
    event = get_object_or_404(Event, id=event_id)
    group = get_object_or_404(Group, event=event, name=group_name)
    heat  = get_object_or_404(Heat, event=event, round_no=round_no, group=group)
    player = Player.objects.filter(user=request.user).first()
    if not player:
        messages.error(request, "当前账号未绑定选手名，请先在『我的』页面创建。")
        return redirect("me")
    members_qs = (GroupMembership.objects
                  .filter(event=event, round_no=round_no, group=group)
                  .select_related("player")
                  .order_by(Lower("player__name")))
    if not members_qs.filter(player=player).exists():
        messages.error(request, "你不在该组本轮名单中，无法设置房号。")
        return redirect("event_detail", event_id=event.id)
    host_player = members_qs.first().player
    is_host = (player.id == host_player.id)
    if request.method == "POST":
        if not is_host:
            messages.error(request, f"只有房主（{host_player.name}）可以设置/修改房号。")
            return redirect("event_detail", event_id=event.id)
        code = (request.POST.get("room_code") or "").strip()
        if not code:
            messages.error(request, "房号不能为空。")
            return redirect("set_room_code", event_id=event.id, round_no=round_no, group_name=group_name)
        if len(code) > 50:
            messages.error(request, "房号过长（≤50字符）。")
            return redirect("set_room_code", event_id=event.id, round_no=round_no, group_name=group_name)
        heat.room_code = code
        heat.save(update_fields=["room_code"])
        messages.success(request, f"已更新第 {round_no} 轮 {group_name} 组房号为：{code}")
        return redirect("event_detail", event_id=event.id)
    return render(request, "turf/set_room_code.html", {
        "event": event, "round_no": round_no, "group": group, "heat": heat,
        "host_player": host_player, "is_host": is_host,
    })

# ===================== 个人主页 =====================
def player_profile(request, player_id: int):
    player = get_object_or_404(Player, id=player_id)
    if player.user and player.user.is_staff:
        if not (request.user.is_authenticated and (request.user.is_staff or request.user == player.user)):
            messages.error(request, "该选手资料仅限本人或管理员查看。")
            return redirect("home")
    is_owner = request.user.is_authenticated and (player.user and request.user == player.user)
    is_staff = request.user.is_authenticated and request.user.is_staff
    can_edit_honors = is_owner or is_staff
    can_view_private = player.public_results or is_owner or is_staff
    if request.method == "POST" and can_edit_honors:
        fields = [
            "honor_umaleague_season_champ", "honor_umaleague_stage_champ",
            "honor_loh96_hero", "honor_aupl_champion", "honor_nxns_champion",
        ]
        for f in fields:
            setattr(player, f, bool(request.POST.get(f)))
        if "bio" in request.POST:
            player.bio = request.POST.get("bio","")
        player.public_results = bool(request.POST.get("public_results"))
        player.save()
        messages.success(request, "已保存个人简介、荣誉与可见性设置。")
        return redirect("player_profile", player_id=player.id)
    payout_sum = 0
    events_detail = []
    if can_view_private:
        payout_sum = (Payout.objects.filter(player=player)
                      .aggregate(total=Sum("total_amount")).get("total") or 0)
        standings = (Standing.objects.filter(player=player)
                     .select_related("event").order_by("-event__id"))
        results_qs = (Result.objects.filter(player=player, is_npc=False)
                      .select_related("heat","heat__event","heat__group")
                      .order_by("-heat__event__id","heat__round_no","heat__group__name"))
        events_map = {}
        for r in results_qs:
            eid = r.heat.event_id
            bucket = events_map.setdefault(eid, {"event": r.heat.event, "rows": []})
            bucket["rows"].append({
                "round_no": r.heat.round_no,
                "group": r.heat.group.name if r.heat.group else "",
                "horse_no": r.horse_no, "place": r.place,
            })
        for st in standings:
            events_detail.append({
                "event": st.event, "rank": st.rank, "total_score": st.total_score,
                "rows": events_map.get(st.event.id, {}).get("rows", []),
            })
    ctx = {
        "player": player, "bio": player.bio or "", "payout_sum": payout_sum,
        "events_detail": events_detail, "can_edit_honors": can_edit_honors,
        "can_view_private": can_view_private,
    }
    return render(request, "guest/player_profile.html", ctx)