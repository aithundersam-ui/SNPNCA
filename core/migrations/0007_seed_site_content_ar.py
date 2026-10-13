from django.db import migrations

# The original French wording, from 0002_seed_site_content.
DESCRIPTION_FR = (
    "Un syndicat autonome et représentative, le SNPNCA défend les droits, valorise le rôle "
    "et améliore les conditions de travail du personnel navigant commercial Algérien"
)
MISSION_FR = (
    "Chaque vol commence par un engagement : celui d’être au service des autres. "
    "Le SNPNCA veille à ce que cet engagement soit reconnu, respecté et défendu."
)
DESCRIPTION_AR = (
    "نقابة مستقلة وتمثيلية، تدافع SNPNCA عن حقوق طاقم الملاحة التجارية الجزائري، "
    "وتُثمّن دوره وتعمل على تحسين ظروف عمله."
)
MISSION_AR = (
    "كل رحلة تبدأ بالتزام: التزام بخدمة الآخرين. "
    "وتحرص SNPNCA على أن يكون هذا الالتزام معترفًا به ومحترمًا ومُدافَعًا عنه."
)


def seed(apps, schema_editor):
    """Add the Arabic home page text, but only where the French text is still the
    original wording (an admin who rewrote it should write the Arabic too)."""
    SiteContent = apps.get_model("core", "SiteContent")
    content = SiteContent.objects.filter(pk=1).first()
    if not content:
        return
    changed = False
    for field, french, arabic in (
        ("description", DESCRIPTION_FR, DESCRIPTION_AR),
        ("mission", MISSION_FR, MISSION_AR),
    ):
        if not getattr(content, f"{field}_ar") and getattr(content, f"{field}_fr") == french:
            setattr(content, f"{field}_ar", arabic)
            changed = True
    if changed:
        content.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0006_sitecontent_description_ar_sitecontent_mission_ar")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
