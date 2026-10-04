from django.db import migrations

DESCRIPTION_FR = (
    "Un syndicat autonome et représentative, le SNPNCA défend les droits, valorise le rôle "
    "et améliore les conditions de travail du personnel navigant commercial Algérien"
)
DESCRIPTION_EN = (
    "An independent organization representing Algerian flight attendants, committed to protecting "
    "their rights, enhancing their status, and improving their working conditions while upholding "
    "dignity and professionalism at a national level."
)
MISSION_FR = (
    "Chaque vol commence par un engagement : celui d’être au service des autres. "
    "Le SNPNCA veille à ce que cet engagement soit reconnu, respecté et défendu."
)
MISSION_EN = (
    "To represent, defend, and protect the interests of flight attendants. We are the voice of "
    "cabin crew, working every day to improve your working conditions and safeguard your rights."
)


def seed(apps, schema_editor):
    """Fill the home page text with the wording from the union's current site, without
    overwriting anything an admin already wrote."""
    SiteContent = apps.get_model("core", "SiteContent")
    content, _created = SiteContent.objects.get_or_create(pk=1)
    changed = False
    for field, value in (
        ("description_fr", DESCRIPTION_FR),
        ("description_en", DESCRIPTION_EN),
        ("mission_fr", MISSION_FR),
        ("mission_en", MISSION_EN),
    ):
        if not getattr(content, field):
            setattr(content, field, value)
            changed = True
    if changed:
        content.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
