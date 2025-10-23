# turf/utils.py

import math, random
from collections import defaultdict
from django.db.models import Max
from django.db import transaction  # <-- 确保导入 transaction
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

# ==================================================
#   v v v  已按新需求修改（Top 6/12 分组） v v v
# ==================================================

def pair_next_round(event: Event):
    """
    Swiss: 依据当前积分榜，为下一轮分组。
    新逻辑 (Top 6/12):
    - 排名 1-6   -> A组
    - 排名 7-12  -> B组
    """
    
    # 1. 确定下一轮的轮次
    #    (如果已有第1轮, max_round=1, next_no=2)
    max_round = Heat.objects.filter(event=event).aggregate(Max('round_no'))['round_no__max'] or 0
    next_no = max_round + 1

    if next_no == 1:
        raise ValueError("请不要使用此功能创建第1轮，请使用 'Swiss: 初始化第1轮分组并创建Heat'。")

    # 2. 获取当前积分榜（必须按 rank 升序排序）
    standings = list(Standing.objects.filter(event=event).order_by('rank'))
    if not standings:
        raise ValueError("积分榜 (Standings) 为空，请先执行 'Recompute standings'。")

    # 3. 明确获取 A 组和 B 组
    #    (新逻辑要求必须存在名为 'A' 和 'B' 的组)
    try:
        group_a = Group.objects.get(event=event, name="A")
        group_b = Group.objects.get(event=event, name="B")
    except Group.DoesNotExist as e:
        raise ValueError(f"分组失败：Event 必须同时包含 'A' 组和 'B' 组。 (错误: {e})")
    except Group.MultipleObjectsReturned as e:
        raise ValueError(f"分组失败：Event 中 'A' 组或 'B' 组存在重复，请检查 Groups。 (错误: {e})")

    # 4. 根据排名切片获取选手
    players_top_6 = [s.player for s in standings[0:6]]   # 排名 1-6
    players_7_to_12 = [s.player for s in standings[6:12]] # 排名 7-12

    if not players_top_6:
        raise ValueError("积分榜为空或未计算，无法获取前6名选手。")

    # 5. 清理下一轮的旧分组和Heat
    GroupMembership.objects.filter(event=event, round_no=next_no).delete()
    Heat.objects.filter(event=event, round_no=next_no).delete()

    members_created_count = 0

    # 6. 创建 A 组 (排名 1-6)
    if players_top_6:
        Heat.objects.get_or_create(event=event, round_no=next_no, group=group_a)
        for player in players_top_6:
            GroupMembership.objects.create(event=event, round_no=next_no, group=group_a, player=player)
            members_created_count += 1

    # 7. 创建 B 组 (排名 7-12)
    if players_7_to_12:
        Heat.objects.get_or_create(event=event, round_no=next_no, group=group_b)
        for player in players_7_to_12:
            GroupMembership.objects.create(event=event, round_no=next_no, group=group_b, player=player)
            members_created_count += 1
    
    return members_created_count

# ==================================================
#   ^ ^ ^  修改结束 ^ ^ ^
# ==================================================

# ==================================================
#   v v v  新增：每轮纯随机分组（任意人数） v v v
# ==================================================

def seed_vanguard_random_per_round(event: Event):
    """
    前哨战（任意人数）：为所有轮次（event.rounds）生成纯随机分组。
    每一轮都会重新洗牌所有选手，并尽量平均分配到所有组（event.group_count）。
    这将覆盖所有轮次的 Heat 和 GroupMembership。
    """
    
    # 1. 获取所有激活的选手
    players = [e.player for e in Enrollment.objects.filter(event=event, status="active")]
    players = list(dict.fromkeys(players)) # 去重保险
    n_players = len(players)
    if n_players == 0:
        raise ValueError("没有已报名的选手 (status='active')。")

    # 2. 获取总轮数和所有分组
    total_rounds = event.rounds
    groups = list(Group.objects.filter(event=event).order_by('name'))
    n_groups = len(groups)
    if n_groups == 0:
        raise ValueError(f"请先为该 Event 建立分组（Groups）。（当前 Group 数量为 0）")
    if total_rounds <= 0:
        raise ValueError(f"Event 的轮数 (rounds) 必须大于 0。")

    # 3. 计算每组的基础人数和余数
    base_size = n_players // n_groups
    remainder = n_players % n_groups
    
    group_sizes = [base_size] * n_groups
    for i in range(remainder):
        group_sizes[i] += 1  # e.g., 28人, 3组 -> [9, 9, 9] -> [10, 9, 9]

    with transaction.atomic():
        # 4. 清理所有轮次的旧数据
        all_round_numbers = list(range(1, total_rounds + 1))
        Heat.objects.filter(event=event, round_no__in=all_round_numbers).delete()
        GroupMembership.objects.filter(event=event, round_no__in=all_round_numbers).delete()

        # 5. 为每一轮独立生成分组
        for r in all_round_numbers:
            # 关键：每轮都重新洗牌
            random.shuffle(players)
            
            player_idx_start = 0
            for i, g in enumerate(groups):
                size = group_sizes[i]
                if size == 0:
                    continue
                    
                player_idx_end = player_idx_start + size
                group_players = players[player_idx_start : player_idx_end]
                
                # 创建 Heat
                Heat.objects.get_or_create(event=event, round_no=r, group=g)
                
                # 创建 GroupMembership
                members_to_create = [
                    GroupMembership(event=event, round_no=r, group=g, player=p)
                    for p in group_players
                ]
                GroupMembership.objects.bulk_create(members_to_create)
                
                player_idx_start = player_idx_end

    return n_players # 返回处理的选手总数

# ==================================================
#   ^ ^ ^  新增结束 ^ ^ ^
# ==================================================


# === 追加到文件底部（或与其它分组函数放一起） ===
# import random  <-- 已在顶部导入
# from django.db import transaction <-- 已在顶部导入
# from .models import Enrollment, Group, Heat, GroupMembership <-- 已在顶部导入

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
    生成/覆盖：Heat + GroupMembership（round_no=1..5）。
    要求：恰好36名报名；不自动补NPC。
    
    [注：已修复此函数中 round -> round_no 的字段名错误]
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
        # [已修复] round__in -> round_no__in
        Heat.objects.filter(event=event, round_no__in=[1,2,3,4,5]).delete()
        GroupMembership.objects.filter(event=event, round_no__in=[1,2,3,4,5]).delete()

        for r in range(1, 6):
            plan = VANGUARD_ENTROPY_SCHEDULE[r]
            for name in ("A", "B", "C"):
                g = groups[name]
                # [已修复] round=r -> round_no=r
                heat, _ = Heat.objects.get_or_create(event=event, round_no=r, group=g)
                serials = set(plan[name])
                chosen = [p for p, s in p2serial.items() if s in serials]
                if len(chosen) != 12:
                    raise RuntimeError(f"第{r}轮{name}组应为12人，当前{len(chosen)}。")
                for p in chosen:
                    # [已修复] round=r -> round_no=r
                    GroupMembership.objects.create(event=event, round_no=r, group=g, player=p)

    return p2serial  # 用于页面展示“选手→序号”