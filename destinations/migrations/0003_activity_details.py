import django.utils.timezone
from django.db import migrations, models

import destinations.models


class Migration(migrations.Migration):
    dependencies = [("destinations", "0002_seed_examples")]

    operations = [
        migrations.RenameField("activity", "text_fr", "title_fr"),
        migrations.RenameField("activity", "text_en", "title_en"),
        migrations.RenameField("activity", "text_ar", "title_ar"),
        migrations.AlterField("activity", "title_fr", models.CharField(max_length=200, verbose_name="activity (French)")),
        migrations.AlterField("activity", "title_en", models.CharField(blank=True, max_length=200, verbose_name="activity (English)")),
        migrations.AlterField("activity", "title_ar", models.CharField(blank=True, max_length=200, verbose_name="activity (Arabic)")),
        migrations.AddField("activity", "description_fr", models.TextField(blank=True, verbose_name="description (French)")),
        migrations.AddField("activity", "description_en", models.TextField(blank=True, verbose_name="description (English)")),
        migrations.AddField("activity", "description_ar", models.TextField(blank=True, verbose_name="description (Arabic)")),
        migrations.AddField("activity", "photo", models.ImageField(blank=True, upload_to=destinations.models.photo_path, verbose_name="photo")),
        migrations.AddField(
            "activity", "maps_url",
            models.URLField(blank=True, max_length=500, validators=[destinations.models.validate_maps_url], verbose_name="Google Maps link"),
        ),
        migrations.AddField("activity", "updated_at", models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False),
        migrations.AlterField("activity", "position", models.PositiveSmallIntegerField(default=0, verbose_name="order")),
    ]
