from django.db import migrations

BUREAU = [
    ("Bouzourene Fodil", "president", 0, 0),
    ("Zouane Fouad Eddine", "secretary_general", 1, 0),
    ("Driche Chakib", "treasurer", 2, 0),
    ("Benabed Daiem Youcef", "member", 3, 1),
    ("Nachi Walid", "member", 3, 2),
    ("Aougabi Mouad Mohamed Amine", "member", 3, 3),
]


def seed(apps, schema_editor):
    TeamMember = apps.get_model("team", "TeamMember")
    if TeamMember.objects.exists():
        return
    for name, role, rank, position in BUREAU:
        TeamMember.objects.create(full_name=name, role=role, rank=rank, position=position)


class Migration(migrations.Migration):
    dependencies = [("team", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
