from django.db import models
from django.contrib.auth.models import User

class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    bio = models.TextField(blank=True, default="")
    public_results = models.BooleanField(default=True, help_text="允许他人查看本人的历史战绩与总奖金")


    # === 默认荣誉（选手可自勾选，管理员可改） ===
    honor_umaleague_season_champ  = models.BooleanField(default=False)  # UMA League 赛季冠军
    honor_umaleague_stage_champ   = models.BooleanField(default=False)  # UMA League 赛段冠军
    honor_loh96_hero              = models.BooleanField(default=False)  # LOH96 杰
    honor_aupl_champion           = models.BooleanField(default=False)  # AUPL 冠军
    honor_nxns_champion           = models.BooleanField(default=False)  # NXNS 冠军

    def honors_dict(self):
        return {
            "honor_umaleague_season_champ": self.honor_umaleague_season_champ,
            "honor_umaleague_stage_champ":  self.honor_umaleague_stage_champ,
            "honor_loh96_hero":             self.honor_loh96_hero,
            "honor_aupl_champion":          self.honor_aupl_champion,
            "honor_nxns_champion":          self.honor_nxns_champion,
        }

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
    show_on_login = models.BooleanField(default=True)
    show_on_home = models.BooleanField(default=False)
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

# MIGRATION: 0_past_events_champions
# 在 models.py 文件末尾添加以下内容

class PastEvent(models.Model):
    title = models.CharField(max_length=100, verbose_name="赛事标题")
    poster = models.ImageField(upload_to='posters/events/', blank=True, null=True, verbose_name="赛事海报")
    description = models.TextField(verbose_name="赛事简介")
    event_date = models.DateField(verbose_name="赛事日期")
    # 关联到系统内原有的赛事，方便跳转
    original_event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联的系统赛事")
    
    class Meta:
        ordering = ["-event_date"] # 按赛事日期降序排列
        verbose_name = "历届赛事"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title

class PastChampion(models.Model):
    # 关联到对应的历届赛事
    past_event = models.OneToOneField(PastEvent, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联的历届赛事")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, verbose_name="冠军选手")
    poster = models.ImageField(upload_to='posters/champions/', blank=True, null=True, verbose_name="夺冠海报")
    testimonial = models.TextField(verbose_name="夺冠感言")
    gdoc_url = models.URLField(max_length=1024, blank=True, default="", verbose_name="冠军战马Google文档链接")
    
    class Meta:
        # 通过关联的赛事日期进行排序
        ordering = ["-past_event__event_date"]
        verbose_name = "历届冠军"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.past_event.title} - {self.player.name}"

# =========================
#   v v v 新增：宣传/广告模型 v v v
# =========================
class PromoAd(models.Model):
    title = models.CharField(max_length=100, verbose_name="广告标题")
    poster = models.ImageField(upload_to='posters/ads/', verbose_name="宣传海报")
    url = models.URLField(max_length=1024, blank=True, default="", verbose_name="广告链接")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "宣传广告"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
# ^^^^^ 新增结束 ^^^^^