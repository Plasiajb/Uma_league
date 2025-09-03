
import math, random
from collections import defaultdict
from django.db.models import Max
from .models import Event, Heat, Result, Standing, Payout, Enrollment, Group, GroupMembership

def recompute_standings(event: Event):
    per_round = defaultdict(lambda: defaultdict(int))
    heats = Heat.objects.filter(event=event)
    results = Result.objects.filter(heat__in=heats, is_npc=False).select_related('player','heat')
    for r in results:
        per_round[r.player_id][r.heat.round_no] += r.place
    totals = []
    for pid, rounds in per_round.items():
        total = sum(rounds.values())
        totals.append((pid, total))
    totals.sort(key=lambda x: x[1])
    Standing.objects.filter(event=event).delete()
    for rank, (pid, total) in enumerate(totals, start=1):
        Standing.objects.create(event=event, player_id=pid, total_score=total, rank=rank)
    return totals

def compute_payouts_for_event(event: Event, k=2.0, eps=1e-6, tie_eps=0.02, base=600, min6=30, final_extras=(200,100,100,0,0,0)):
    standings = list(Standing.objects.filter(event=event).order_by('rank')[:6])
    if len(standings) < 6:
        return []
    R = max(1, event.rounds)
    S_prime = [s.total_score / R for s in standings]
    Smin, Smax = min(S_prime), max(S_prime)
    denom = max(Smax - Smin, eps)
    z = [(v - Smin) / denom for v in S_prime]
    if max(z) - min(z) < tie_eps:
        base_amounts = [base / 6.0] * 6
    else:
        w = [math.exp(-k * zi) for zi in z]
        wsum = sum(w)
        base_amounts = [base * wi / wsum for wi in w]
        if base_amounts[5] < min6:
            delta = min6 - base_amounts[5]
            T = sum(base_amounts[:5]) or 1.0
            base_amounts = [base_amounts[i] - delta * (base_amounts[i] / T) if i < 5 else base_amounts[i] + delta for i in range(6)]
    base_amounts = [round(x, 2) for x in base_amounts]
    extras = [0]*6
    if event.format == "final":
        extras = list(final_extras)
    Payout.objects.filter(event=event).delete()
    out = []
    for i, s in enumerate(standings):
        total = round(base_amounts[i] + extras[i], 2)
        p = Payout.objects.create(event=event, player=s.player, base_pool=base, base_amount=base_amounts[i], extra_bonus=extras[i], total_amount=total)
        out.append(p)
    return out

def seed_round1(event: Event):
    players = [e.player for e in Enrollment.objects.filter(event=event, status="active")]
    if not players:
        return 0
    random.shuffle(players)
    groups = list(Group.objects.filter(event=event).order_by('name'))
    if not groups:
        raise ValueError("请先为该 Event 建立分组（Groups）。")
    GroupMembership.objects.filter(event=event, round_no=1).delete()
    for idx, p in enumerate(players):
        g = groups[idx % len(groups)]
        GroupMembership.objects.create(event=event, round_no=1, group=g, player=p)
    for g in groups:
        Heat.objects.get_or_create(event=event, round_no=1, group=g)
    return len(players)

def pair_next_round(event: Event):
    max_round = Heat.objects.filter(event=event).aggregate(Max('round_no'))['round_no__max'] or 1
    next_no = max_round + 1
    st = list(Standing.objects.filter(event=event).order_by('total_score','rank'))
    if not st:
        raise ValueError("请先执行 Recompute standings。")
    groups = list(Group.objects.filter(event=event).order_by('name'))
    if not groups:
        raise ValueError("请先为该 Event 建立分组（Groups）。")
    n_groups = len(groups)
    GroupMembership.objects.filter(event=event, round_no=next_no).delete()
    for i, s in enumerate(st):
        g = groups[i % n_groups]
        GroupMembership.objects.create(event=event, round_no=next_no, group=g, player=s.player)
    for g in groups:
        Heat.objects.get_or_create(event=event, round_no=next_no, group=g)
    return len(st)

# === 追加到文件底部（或与其它分组函数放一起） ===
import random
from django.db import transaction
from .models import Enrollment, Group, Heat, GroupMembership

# 5轮×3组×12人的固定分组表（编号 1..36）
VANGUARD_ENTROPY_SCHEDULE = {
    1: {
        "A": [1,2,3,4,13,14,15,16,25,26,27,28],
        "B": [5,6,7,8,17,18,19,20,29,30,31,32],
        "C": [9,10,11,12,21,22,23,24,33,34,35,36],
    },
    2: {
        "A": [2,3,4,5,18,19,20,21,25,34,35,36],
        "B": [6,7,8,9,13,22,23,24,26,27,28,29],
        "C": [1,10,11,12,14,15,16,17,30,31,32,33],
    },
    3: {
        "A": [3,4,5,6,13,14,23,24,31,32,33,34],
        "B": [7,8,9,10,15,16,17,18,25,26,35,36],
        "C": [1,2,11,12,19,20,21,22,27,28,29,30],
    },
    4: {
        "A": [4,5,6,7,16,17,18,19,25,26,27,36],
        "B": [8,9,10,11,20,21,22,23,28,29,30,31],
        "C": [1,2,3,12,13,14,15,24,32,33,34,35],
    },
    5: {
        "A": [5,6,7,8,21,22,23,24,33,34,35,36],
        "B": [9,10,11,12,13,14,15,16,25,26,27,28],
        "C": [1,2,3,4,17,18,19,20,29,30,31,32],
    },
}

def seed_vanguard_entropy(event, *, rng=None):
    """
    前哨战：报名36人 → 随机发1..36序号 → 按固定熵最大表生成5轮 A/B/C 分组。
    生成/覆盖：Heat + GroupMembership（round=1..5）。
    要求：恰好36名报名；不自动补NPC。
    """
    if rng is None:
        rng = random.Random()

    enrolls = list(Enrollment.objects.filter(event=event).select_related("player"))
    players = [e.player for e in enrolls]
    players = list(dict.fromkeys(players))  # 去重保险
    n = len(players)
    if n != 36:
        raise ValueError(f"前哨战需要恰好36名报名，当前 {n}。")

    order = list(range(36))
    rng.shuffle(order)
    p2serial = {players[i]: order[i] + 1 for i in range(36)}

    groups = {}
    for name in ("A", "B", "C"):
        groups[name], _ = Group.objects.get_or_create(event=event, name=name)

    with transaction.atomic():
        Heat.objects.filter(event=event, round__in=[1,2,3,4,5]).delete()
        GroupMembership.objects.filter(event=event, round__in=[1,2,3,4,5]).delete()

        for r in range(1, 6):
            plan = VANGUARD_ENTROPY_SCHEDULE[r]
            for name in ("A", "B", "C"):
                g = groups[name]
                heat, _ = Heat.objects.get_or_create(event=event, round=r, group=g)
                serials = set(plan[name])
                chosen = [p for p, s in p2serial.items() if s in serials]
                if len(chosen) != 12:
                    raise RuntimeError(f"第{r}轮{name}组应为12人，当前{len(chosen)}。")
                for p in chosen:
                    GroupMembership.objects.create(event=event, round=r, group=g, player=p)

    return p2serial  # 用于页面展示“选手→序号”
