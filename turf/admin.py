# turf/admin.py

from django.contrib import admin, messages
from django.db import models
from django.db.models import Q
from itertools import groupby
from django.db import transaction
from .utils import recompute_standings
from .models import Event, GroupMembership, Heat, Result, SelfReport

from .models import (
    Player, Season, Stage, Event, Group, Enrollment, Heat, Result,
    Standing, Payout, GroupMembership, PublishedRank, Announcement, SelfReport,
    PastEvent, PastChampion  # <--- 在此导入新模型
)
# vvvvv  在这里添加新的 import vvvvv
from .utils import (
    recompute_standings, compute_payouts_for_event, seed_round1, pair_next_round,
    seed_vanguard_random_per_round
)

# =========================
# 基础模型注册
# =========================

# ... 您已有的 PlayerAdmin, SeasonAdmin, StageAdmin 等代码保持不变 ...
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    search_fields = ["name","user__username"]
    list_display  = ["id","name","user","public_results",
                     "honor_umaleague_season_champ","honor_umaleague_stage_champ",
                     "honor_loh96_hero","honor_aupl_champion","honor_nxns_champion"]
    list_filter   = ["public_results",
                     "honor_umaleague_season_champ","honor_umaleague_stage_champ",
                     "honor_loh96_hero","honor_aupl_champion","honor_nxns_champion"]

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["id","name","start_date","end_date"]

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["id","season","month","type","track_name"]

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["id","name","stage","format","rounds","group_count"]
    search_fields = ["name"]
    # vvvvv  在这里添加新的 action name vvvvv
    actions = [
        "action_recompute_standings",
        "action_compute_payouts",
        "action_seed_round1",
        "action_pair_next",
        "action_seed_vanguard_random" # <-- 新增
    ]
    # ... rest of your EventAdmin methods ...    # ... EventAdmin 的其他代码不变 ...
    @admin.action(description="Recompute standings from results")
    def action_recompute_standings(self, request, queryset):
        for event in queryset:
            recompute_standings(event)
        self.message_user(request, "Standings recomputed.")

    @admin.action(description="Compute payouts (top-6)")
    def action_compute_payouts(self, request, queryset):
        ok = 0
        for event in queryset:
            out = compute_payouts_for_event(event)
            if out: ok += 1
        self.message_user(request, f"Payouts computed for {ok} event(s).")

    @admin.action(description="Swiss: 初始化第1轮分组并创建Heat")
    def action_seed_round1(self, request, queryset):
        cnt = 0
        for e in queryset:
            cnt += seed_round1(e) or 0
        self.message_user(request, f"已为所选赛事生成第1轮分组/Heat（总计 {cnt} 名选手）。")

    @admin.action(description="Swiss: 依据当前积分为下一轮自动分组并创建Heat")
    def action_pair_next(self, request, queryset):
        cnt = 0
        for e in queryset:
            try:
                cnt += pair_next_round(e) or 0
                self.message_user(request, f"[{e.name}] 已生成下一轮分组（总计 {cnt} 名选手）。")
            except Exception as ex:
                self.message_user(request, f"[{e.name}] 分组失败：{ex}", level=messages.ERROR)


    # vvvvv  在这里添加新的 action method vvvvv
    @admin.action(description="前哨战：每轮纯随机分组 (任意人数)")
    def action_seed_vanguard_random(self, request, queryset):
        events_processed = 0
        try:
            for e in queryset:
                total_rounds = e.rounds
                player_count = seed_vanguard_random_per_round(e)
                events_processed += 1
                self.message_user(request, f"[{e.name}] 已生成 {total_rounds} 轮纯随机分组（总计 {player_count} 名选手）。")
            
            if events_processed > 1:
                self.message_user(request, f"总计 {events_processed} 个赛事处理完毕。")

        except Exception as ex:
            self.message_user(request, f"分组失败：{ex}", level=messages.ERROR)
    # ^^^^^  新增结束 ^^^^^


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["id","event","name"]

# ... 您其他的 Admin 注册代码保持不变 ...
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["id","event","player","status"]
    list_filter = ["event","status"]

@admin.register(Heat)
class HeatAdmin(admin.ModelAdmin):
    list_display = ["id","event","round_no","group","room_code"]
    list_filter = ["event","round_no","group"]

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["id","heat","player","horse_no","place","is_npc"]
    list_filter = ["heat__event","heat__round_no","is_npc"]
    search_fields = ["player__name"]

@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ["event","player","total_score","rank","qualified_flag","notes"]
    list_filter = ["event"]

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["event","player","base_pool","base_amount","extra_bonus","total_amount"]
    list_filter = ["event"]

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["event","round_no","group","player"]
    list_filter = ["event","round_no","group"]

@admin.register(PublishedRank)
class PublishedRankAdmin(admin.ModelAdmin):
    list_display = ["event","rank","player","note"]
    list_filter = ["event"]
    ordering = ["event","rank"]

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "is_active", "show_on_login", "show_on_home", "start_at", "end_at", "updated_at"]
    list_filter = ["is_active", "show_on_login", "show_on_home"]
    search_fields = ["title", "body"]
    actions = ["activate", "deactivate"]

    @admin.action(description="启用所选公告")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="停用所选公告")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


# +++ 新增：历届回顾后台管理 +++
@admin.register(PastEvent)
class PastEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_date', 'original_event')
    search_fields = ('title',)
    list_filter = ('event_date',)
    autocomplete_fields = ['original_event']

@admin.register(PastChampion)
class PastChampionAdmin(admin.ModelAdmin):
    list_display = ('player', 'past_event', 'gdoc_url')
    search_fields = ('player__name', 'past_event__title')
    autocomplete_fields = ['player', 'past_event']
# +++ 新增结束 +++


# =========================
#   前哨战：熵最大分组
# =========================
# ... 您后续的 action_seed_vanguard_entropy, approve_reports 等代码保持不变 ...
# 固定分组表（5轮 × 3组 × 12人）
VANGUARD_ENTROPY_SCHEDULE = {
    1: {"A": [1,2,3,4,13,14,15,16,25,26,27,28],
        "B": [5,6,7,8,17,18,19,20,29,30,31,32],
        "C": [9,10,11,12,21,22,23,24,33,34,35,36]},
    2: {"A": [2,3,4,5,18,19,20,21,25,34,35,36],
        "B": [6,7,8,9,13,22,23,24,26,27,28,29],
        "C": [1,10,11,12,14,15,16,17,30,31,32,33]},
    3: {"A": [3,4,5,6,13,14,23,24,31,32,33,34],
        "B": [7,8,9,10,15,16,17,18,25,26,35,36],
        "C": [1.2,11,12,19,20,21,22,27,28,29,30]},
    4: {"A": [4,5,6,7,16,17,18,19,25,26,27,36],
        "B": [8,9,10,11,20,21,22,23,28,29,30,31],
        "C": [1,2,3,12,13,14,15,24,32,33,34,35]},
    5: {"A": [5,6,7,8,21,22,23,24,33,34,35,36],
        "B": [9,10,11,12,13,14,15,16,25,26,27,28],
        "C": [1,2,3,4,17,18,19,20,29,30,31,32]},
}

@admin.action(description="前哨战分组（熵最大5轮）")
def action_seed_vanguard_entropy(modeladmin, request, queryset):
    # 不依赖 utils 内旧函数，直接这里实现（用 round_no 字段）
    import random
    ok = fail = 0

    for event in queryset:
        try:
            # 报名选手（去重）
            enrolls = list(Enrollment.objects.filter(event=event).select_related("player"))
            players = [e.player for e in enrolls]
            players = list(dict.fromkeys(players))
            if len(players) != 36:
                raise ValueError(f"前哨战需要恰好36名报名，当前 {len(players)}。")

            order = list(range(36))
            random.shuffle(order)
            p2serial = {players[i]: order[i] + 1 for i in range(36)}

            # 组 A/B/C
            groups = {}
            for name in ("A","B","C"):
                groups[name], _ = Group.objects.get_or_create(event=event, name=name)

            with transaction.atomic():
                Heat.objects.filter(event=event, round_no__in=[1,2,3,4,5]).delete()
                GroupMembership.objects.filter(event=event, round_no__in=[1,2,3,4,5]).delete()

                for r in range(1, 6):
                    plan = VANGUARD_ENTROPY_SCHEDULE[r]
                    for name in ("A","B","C"):
                        g = groups[name]
                        heat, _ = Heat.objects.get_or_create(event=event, round_no=r, group=g)
                        serials = set(plan[name])
                        chosen = [p for p, s in p2serial.items() if s in serials]
                        if len(chosen) != 12:
                            raise RuntimeError(f"第{r}轮{name}组应为12人，当前{len(chosen)}。")
                        for p in chosen:
                            GroupMembership.objects.create(event=event, round_no=r, group=g, player=p)

            ok += 1
            sample = ", ".join([f"{p.name}:{sn}" for p, sn in list(p2serial.items())[:5]])
            messages.success(request, f"[{event}] 分组生成完成。示例映射 {sample} …")

        except Exception as e:
            fail += 1
            messages.error(request, f"[{event}] 失败：{e}")

    messages.info(request, f"完成：成功 {ok}，失败 {fail}")

# 将动作追加到已注册的 EventAdmin
EventAdmin.actions = list(getattr(EventAdmin, "actions", [])) + [action_seed_vanguard_entropy]

# =========================
#   自助填报审核 → 正式成绩
# =========================


@admin.action(description="审核通过并写入正式成绩")
def approve_reports(self, request, queryset):
    # 仅处理未审核
    qs = queryset.filter(verified=False).order_by("event_id", "player_id", "round_no", "horse_index")
    count = 0
    touched_events = set()  # 记录受影响的赛事，用于稍后重算 standings

    def key(r): return (r.event_id, r.player_id, r.round_no)
    for (event_id, player_id, rnd), grp in groupby(qs, key=key):
        grp = list(grp)
        # 单马赛：该轮通常只有一条；双马赛：该轮可能两条，取和
        total_place = sum(int(r.place) for r in grp)

        try:
            gm = GroupMembership.objects.get(event_id=event_id, player_id=player_id, round_no=rnd)
            heat = Heat.objects.get(event_id=event_id, round_no=rnd, group=gm.group)
        except GroupMembership.DoesNotExist:
            messages.error(request, f"[event={event_id}, player={player_id}, round={rnd}] 无分组记录。")
            continue
        except Heat.DoesNotExist:
            messages.error(request, f"[event={event_id}, round={rnd}] 无 Heat 记录。")
            continue

        # 用 (heat, player, horse_no) 作为唯一键；固定写 horse_no=1
        Result.objects.update_or_create(
            heat=heat,
            player_id=player_id,
            horse_no=1,
            defaults={"place": total_place, "is_npc": False},
        )

        # 标记该轮自填记录为已审核
        SelfReport.objects.filter(event_id=event_id, player_id=player_id, round_no=rnd).update(verified=True)
        count += 1
        touched_events.add(event_id)

    # 审核完，自动重算受影响赛事的 standings（把 5 轮求和、排名一并更新）
    for eid in touched_events:
        try:
            event = Event.objects.get(id=eid)
            recompute_standings(event)
        except Event.DoesNotExist:
            continue

    messages.success(request, f"已审核并写入 {count} 轮成绩，并已重算总分与排名。")

@admin.register(SelfReport)
class SelfReportAdmin(admin.ModelAdmin):
    list_display = ("event","player","round_no","horse_index","place","verified","submitted_at")
    list_filter = ("event","verified")
    search_fields = ("player__name",)
    actions = [approve_reports]