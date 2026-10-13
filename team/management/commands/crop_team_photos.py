from django.core.management.base import BaseCommand

from team.models import TeamMember


class Command(BaseCommand):
    help = "Rebuild the face-centred square crops of all team photos from their originals."

    def handle(self, *args, **options):
        for person in TeamMember.objects.exclude(photo=""):
            found = person.make_crop()
            self.stdout.write(f"{person.full_name}: {'face found' if found else 'no face, centred crop'}")
