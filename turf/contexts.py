# turf/contexts.py

from django.utils import timezone
from .models import Announcement, PromoAd  # <--- 1. 导入 PromoAd

def promo_context(request):
    now = timezone.now()
    qs = Announcement.objects.filter(is_active=True)
    # 时间窗口过滤（如果设置了）
    qs = qs.filter(start_at__lte=now) if qs.filter(start_at__isnull=False).exists() else qs
    qs = qs.filter(end_at__gte=now) if qs.filter(end_at__isnull=False).exists() else qs
    
    # 登录页用
    login_anno = qs.filter(show_on_login=True).order_by("-updated_at").first()
    
    # vvvvv 2. 已删除 home_announcement 逻辑 vvvvv
    # home_anno = qs.filter(show_on_home=True).order_by("-updated_at").first()
    # ^^^^^ 删除结束 ^^^^^
    
    # vvvvv 3. 新增：获取随机广告 vvvvv
    active_ads = list(PromoAd.objects.filter(is_active=True).order_by('?'))
    # ^^^^^ 新增结束 ^^^^^

    return {
        "promo_announcement": login_anno,
        # "home_announcement": home_anno, # <-- 确保这一行被删除或注释掉
        "active_ads": active_ads,        # <-- 4. 添加广告到全局上下文
    }