from django.db import migrations

FACEBOOK = "https://www.facebook.com/share/1CbdB3dM1j/"
INSTAGRAM = "https://www.instagram.com/snpnca/"


def seed(apps, schema_editor):
    SiteContent = apps.get_model("core", "SiteContent")
    content, _created = SiteContent.objects.get_or_create(pk=1)
    if not content.facebook_url and not content.instagram_url:
        content.facebook_url, content.instagram_url = FACEBOOK, INSTAGRAM
        content.save(update_fields=["facebook_url", "instagram_url"])


class Migration(migrations.Migration):
    dependencies = [("core", "0010_social_links")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
