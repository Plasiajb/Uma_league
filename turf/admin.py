
from django.contrib import admin
from django.db import models
from .models import Player, Season, Stage, Event, Group, Enrollment, Heat, Result, Standing, Payout, GroupMembership, PublishedRank
from .utils import recompute_standings, compute_payouts_for_event, seed_round1, pair_next_round

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    search_fields = ["name","user__username"]
    list_display = ["id","name","user"]

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["id","name","start_date","end_date"]

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["id","season","month","type","track_name"]

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["id","name","stage","format","rounds","group_count"]
    actions = ["action_recompute_standings", "action_compute_payouts", "action_seed_round1", "action_pair_next"]

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
            cnt += pair_next_round(e) or 0
        self.message_user(request, f"已为所选赛事生成下一轮分组/Heat（总计 {cnt} 名选手）。")

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["id","event","name"]

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

from .models import Announcement

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

