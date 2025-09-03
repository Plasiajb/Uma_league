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

def event_detail(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)
    standings = Standing.objects.filter(event=event).order_by('rank')
    heats = Heat.objects.filter(event=event).order_by('round_no','group__name')
    results = Result.objects.filter(heat__in=heats, is_npc=False).select_related('player','heat','heat__group')
    gms = GroupMembership.objects.filter(event=event).order_by('round_no','group__name','player__name')
    published = PublishedRank.objects.filter(event=event).order_by('rank')
    ctx = {"event": event,"standings": standings,"heats": heats,"results": results,"group_members": gms,"published": published}
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

@login_required
def report_results(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)
    player = get_object_or_404(Player, user=request.user)

    # 该选手在本赛事的分组列表（用于生成表单）
    memberships = list(
        GroupMembership.objects.filter(event=event, player=player).order_by("round_no")
    )
    if not memberships:
        messages.error(request, "你未参与本赛事或尚未分组。")
        return redirect("event_detail", event_id=event.id)

    horses = _per_round_horses(event)

    # 未审核的草稿值
    existing = {
        (sr.round_no, sr.horse_index): sr.place
        for sr in SelfReport.objects.filter(event=event, player=player, verified=False)
    }

    if request.method == "POST":
        updates = 0
        for m in memberships:
            for h in range(1, horses + 1):
                key = f"r{m.round_no}_h{h}"
                val = request.POST.get(key, "").strip()
                if not val:
                    continue
                place = int(val)
                if not (1 <= place <= 12):
                    messages.error(request, f"第{m.round_no}轮 第{h}匹：名次必须在1-12之间。")
                    return redirect("report_results", event_id=event.id)
                SelfReport.objects.update_or_create(
                    event=event, player=player, round_no=m.round_no, horse_index=h,
                    defaults={"place": place, "verified": False}
                )
                updates += 1

        if updates:
            messages.success(request, f"已提交 {updates} 条名次，等待裁判审核。")
        else:
            messages.info(request, "没有任何更新。")
        return redirect("event_detail", event_id=event.id)

    return render(request, "turf/report_results.html", {
        "event": event,
        "memberships": memberships,
        "horses": horses,
        "existing": existing,
    })

