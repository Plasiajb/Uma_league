from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .models import (
    Season, Stage, Event, Group, Heat, Result, Standing, Payout,
    Player, Enrollment, GroupMembership, PublishedRank, SelfReport
)

def current_stage():
    return Stage.objects.order_by('-id').first()

def home(request):
    stage = current_stage()
    events = Event.objects.filter(stage=stage) if stage else []
    ctx = {"stage": stage, "events": events}
    return render(request, "guest/home.html", ctx)

# views.py → event_detail 内
def event_detail(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)
    standings = Standing.objects.filter(event=event).order_by('rank')
    heats = Heat.objects.filter(event=event).order_by('round_no','group__name')
    results = Result.objects.filter(heat__in=heats, is_npc=False).select_related('player','heat','heat__group')
    gms = GroupMembership.objects.filter(event=event).order_by('round_no','group__name','player__name')
    published = PublishedRank.objects.filter(event=event).order_by('rank')

    # 新增：是否显示“战绩填报”按钮（登录且本赛事有分组）
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

def players(request):
    # 总奖金
    payouts = Payout.objects.values('player__name').annotate(total=Sum('total_amount'))
    # 参赛“场次”统计（以 Standing 行数近似；也可 Count('event', distinct=True)）
    standings_counts = Standing.objects.values('player__name').annotate(events=Count('event', distinct=True))
    totals = {}
    for p in payouts:
        totals[p['player__name']] = {"total": p['total'], "events": 0}
    for c in standings_counts:
        totals.setdefault(c['player__name'], {"total": 0, "events": 0})
        totals[c['player__name']]["events"] = c['events']
    rows = [{"player": k, "total": v["total"], "events": v["events"]} for k,v in totals.items()]
    rows.sort(key=lambda r: (- (r["total"] or 0), r["player"]))
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
    player = getattr(request.user, "player", None) or Player.objects.filter(user=request.user).first()
    if request.method=="POST":
        bio = request.POST.get("bio","")
        if player:
            player.bio = bio
            player.save()
            messages.success(request,"已保存")
    return render(request,"guest/me.html", {"player": player})

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
    """
    每轮几匹马：
      - 前哨战/选拔赛：1
      - 结算赛/Final：2
    """
    if event.format in ("settlement", "final"):
        return 2
    return 1

# 在文件顶部已 import 的不动
# 只替换 report_results 这个视图体内 “existing” 和渲染部分

@login_required
def report_results(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    # 允许没有绑定 Player 的账号能提示
    player = Player.objects.filter(user=request.user).first()
    if not player:
        messages.error(request, "当前账号还没有选手名，请先在『我的』页面创建。")
        return redirect("me")

    memberships = list(
        GroupMembership.objects.filter(event=event, player=player).order_by("round_no")
    )
    if not memberships:
        messages.error(request, "你未参与本赛事或尚未分组。")
        return redirect("event_detail", event_id=event.id)

    horses = 2 if event.format in ("settlement", "final") else 1

    # 关键：做成 "r{round}_h{h}" -> place 的扁平字典，模板直接用，不需要过滤器
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
        "event": event,
        "memberships": memberships,
        "horses": horses,
        "prefill": prefill,   # <— 传这个
    })

from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Event, Group, Heat, GroupMembership, Player

@login_required
@require_http_methods(["GET", "POST"])
def set_room_code(request, event_id: int, round_no: int, group_name: str):
    """
    只有该 Heat 的“房主”（本组按 player.name 升序的第一个）可以设置/修改房号。
    其他人访问会被友好提示并拒绝提交。
    """
    event = get_object_or_404(Event, id=event_id)
    group = get_object_or_404(Group, event=event, name=group_name)
    heat  = get_object_or_404(Heat, event=event, round_no=round_no, group=group)

    player = Player.objects.filter(user=request.user).first()
    if not player:
        messages.error(request, "当前账号未绑定选手名，请先在『我的』页面创建。")
        return redirect("me")

    # 本组成员（按名字升序），第一个即房主
    members_qs = (GroupMembership.objects
                  .filter(event=event, round_no=round_no, group=group)
                  .select_related("player").order_by("player__name"))
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
        "event": event,
        "round_no": round_no,
        "group": group,
        "heat": heat,
        "host_player": host_player,
        "is_host": is_host,
    })

from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .models import Player, Event, Standing, Result, Payout

def player_profile(request, player_id: int):
    """
    选手个人主页：
    - 显示选手基础信息（含简介）
    - 历史战绩：该选手参加过的所有赛事（Standing 为准），显示名次/总分
    - 总奖金：Payout.total_amount 汇总
    - 成绩明细：按赛事 → 轮次列出每轮 place（排除 NPC）
    权限：
    - 若目标选手绑定的是 staff 账户，仅本人或 staff 可查看；其他人拒绝。
    """
    player = get_object_or_404(Player, id=player_id)

    # 屏蔽工作人员信息：仅本人或管理员可查看
    if player.user and player.user.is_staff:
        if not (request.user.is_authenticated and (request.user.is_staff or request.user == player.user)):
            messages.error(request, "该选手资料仅限本人或管理员查看。")
            return redirect("home")

    # 个人简介
    bio = player.bio or ""

    # 历史战绩（以 Standing 为准）
    standings = (Standing.objects
                 .filter(player=player)
                 .select_related("event")
                 .order_by("-event__id"))

    # 该选手总奖金
    payout_sum = (Payout.objects
                  .filter(player=player)
                  .aggregate(total=Sum("total_amount"))
                  .get("total") or 0)

    # 明细成绩：按赛事聚合 → 每轮（round_no） & 组别 & 名次
    results_qs = (Result.objects
                  .filter(player=player, is_npc=False)
                  .select_related("heat", "heat__event", "heat__group")
                  .order_by("-heat__event__id", "heat__round_no", "heat__group__name"))

    # 组装成 {event_id: {"event": Event, "rows": [...]}}
    events_map = {}
    for r in results_qs:
        eid = r.heat.event_id
        bucket = events_map.setdefault(eid, {
            "event": r.heat.event,
            "rows": []
        })
        bucket["rows"].append({
            "round_no": r.heat.round_no,
            "group": r.heat.group.name if r.heat.group else "",
            "horse_no": r.horse_no,
            "place": r.place,
        })

    # 为了在页面上配合 standings 一起展示，构造一个列表
    events_detail = []
    for st in standings:
        item = {
            "event": st.event,
            "rank": st.rank,
            "total_score": st.total_score,
            "rows": events_map.get(st.event.id, {}).get("rows", []),
        }
        events_detail.append(item)

    ctx = {
        "player": player,
        "bio": bio,
        "payout_sum": payout_sum,
        "events_detail": events_detail,  # 每个元素：{event, rank, total_score, rows:[{round_no,group,horse_no,place}]}
    }
    return render(request, "guest/player_profile.html", ctx)

