
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
