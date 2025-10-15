from django.contrib import admin
from django.urls import path, include

# +++ 新增以下两行导入 +++
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("turf.urls")),
]

# +++ 在文件末尾新增这部分代码 +++
# 这段代码的作用是让 Django 的开发服务器能够处理 /media/ 开头的 URL 请求
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)