from django.db import models
from django.contrib.auth.models import User

class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    bio = models.TextField(blank=True, default="")
    def __str__(self):
        return self.name

class Season(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    def __str__(self):
        return self.name

class Stage(models.Model):
    STAGE_TYPES = [
        ("prelim", "前哨战"),
        ("qualifier", "选拔赛"),
        ("settlement", "赛段结算赛"),
        ("final_pre", "Final预选"),
        ("final", "Season Final"),
    ]
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    month = models.CharField(max_length=20)
    type = models.CharField(max_length=20, choices=STAGE_TYPES)
    track_name = models.CharField(max_length=200)
    ruleset_json = models.TextField(default="{}")
    def __str__(self):
        return f"{self.season.name}-{self.month}-{self.get_type_display()}"

class Event(models.Model):
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    format = models.CharField(max_length=20, choices=[
        ("prelim","前哨战"),
        ("settlement","结算赛"),
        ("final","Final"),
        ("qualifier","选拔赛"),
        ("final_pre","Final预选")
    ])
    rounds = models.IntegerField(default=5)
    group_count = models.IntegerField(default=2)
    def __str__(self):
        return f"{self.name}"

class Group(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    def __str__(self):
        return f"{self.event.name}-{self.name}"

class Enrollment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default="active")
    class Meta:
        unique_together = ("event","player")

class Heat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    round_no = models.IntegerField()
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    room_code = models.CharField(max_length=50, blank=True, default="")
    class Meta:
        unique_together = ("event","round_no","group")

class Result(models.Model):
    heat = models.ForeignKey(Heat, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    horse_no = models.IntegerField(default=1)
    place = models.IntegerField()
    is_npc = models.BooleanField(default=False)
    class Meta:
        unique_together = ("heat","player","horse_no")

class GroupMembership(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    round_no = models.IntegerField()
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    class Meta:
        unique_together = ("event","round_no","player")

class Standing(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    total_score = models.IntegerField()
    rank = models.IntegerField()
    qualified_flag = models.BooleanField(default=False)
    notes = models.CharField(max_length=200, blank=True, default="")
    class Meta:
        unique_together = ("event","player")

class Payout(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    base_pool = models.IntegerField(default=600)
    base_amount = models.FloatField(default=0.0)
    extra_bonus = models.FloatField(default=0.0)
    total_amount = models.FloatField(default=0.0)
    class Meta:
        unique_together = ("event","player")

class PublishedRank(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    rank = models.IntegerField()
    note = models.CharField(max_length=200, blank=True, default="")
    class Meta:
        unique_together = ("event","player")

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField(help_text="支持换行。可写少量HTML（如 <br>、<a>）。")
    is_active = models.BooleanField(default=True)
    show_on_login = models.BooleanField(default=True)   # 是否在登录页显示
    show_on_home = models.BooleanField(default=False)  # 是否在首页显示（可选）
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({'ON' if self.is_active else 'OFF'})"

# ---- 自助战绩填报（待审表） ----
class SelfReport(models.Model):
    event = models.ForeignKey("Event", on_delete=models.CASCADE)
    player = models.ForeignKey("Player", on_delete=models.CASCADE)
    round_no = models.IntegerField()                # 第几轮（1..5/7）
    horse_index = models.IntegerField(default=1)    # 第几匹马：前哨战=1；结算/Final=1或2
    place = models.IntegerField()                   # 填报名次
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)

    class Meta:
        unique_together = ("event", "player", "round_no", "horse_index")

    def __str__(self):
        return f"{self.event} / {self.player} / R{self.round_no} H{self.horse_index} = {self.place}"
