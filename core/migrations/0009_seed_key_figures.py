from django.db import migrations

FIGURES = [
    ("users", 700, "+", "PNC affiliés", "Affiliated cabin crew", "منخرط من طاقم الضيافة"),
    ("map-pin", 5, "", "Villes", "Cities", "مدن"),
]


def seed(apps, schema_editor):
    KeyFigure = apps.get_model("core", "KeyFigure")
    if KeyFigure.objects.exists():
        return
    for position, (icon, value, suffix, fr, en, ar) in enumerate(FIGURES):
        KeyFigure.objects.create(
            icon=icon, value=value, suffix=suffix, label_fr=fr, label_en=en, label_ar=ar, position=position
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0008_key_figures")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
