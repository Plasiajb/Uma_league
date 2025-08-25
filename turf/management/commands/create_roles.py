
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from turf.models import Result, Player

class Command(BaseCommand):
    help = "Create 'recorder' group with permissions and guest user"
    def handle(self, *args, **options):
        recorder, _ = Group.objects.get_or_create(name="recorder")
        for model in [Result, Player]:
            ct = ContentType.objects.get_for_model(model)
            for codename in [f"add_{model._meta.model_name}", f"change_{model._meta.model_name}"]:
                try:
                    perm = Permission.objects.get(content_type=ct, codename=codename)
                    recorder.permissions.add(perm)
                except Permission.DoesNotExist:
                    pass
        if not User.objects.filter(username="guest").exists():
            User.objects.create_user("guest", password="guest")
            self.stdout.write(self.style.SUCCESS("Guest user created (password 'guest')."))
        self.stdout.write(self.style.SUCCESS("Recorder group ready."))
