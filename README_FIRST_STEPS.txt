
# Uma League 本地快速启动（含演示数据）

1) 创建并激活虚拟环境、安装依赖
   python -m venv .venv
   .\.venv\Scripts\activate   （Windows）
   pip install -r requirements.txt

2) 初始化数据库
   python manage.py makemigrations turf
   python manage.py migrate

3) （可选）创建管理员
   python manage.py createsuperuser

4) 载入演示数据（包含赛季/赛事/分组/选手/报名/第1轮结果等）
   python manage.py loaddata fixtures/initial_data.json

5) 启动
   python manage.py runserver

后台登录：/admin
前台：/

注意：首次加载后，你可以在 Events 列表运行：
- Recompute standings（重算积分）
- Swiss: 初始化第1轮分组 / 依据当前积分为下一轮自动分组
- Compute payouts (top-6)（奖金分配）
