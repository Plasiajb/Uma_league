from django.utils import timezone
from .models import Announcement

def promo_context(request):
    now = timezone.now()
    qs = Announcement.objects.filter(is_active=True)
    # 时间窗口过滤（如果设置了）
    qs = qs.filter(start_at__lte=now) if qs.filter(start_at__isnull=False).exists() else qs
    qs = qs.filter(end_at__gte=now) if qs.filter(end_at__isnull=False).exists() else qs
    # 登录页用
    login_anno = qs.filter(show_on_login=True).order_by("-updated_at").first()
    # 首页用（可选）
    home_anno = qs.filter(show_on_home=True).order_by("-updated_at").first()
    return {
        "promo_announcement": login_anno,
        "home_announcement": home_anno,
    }
