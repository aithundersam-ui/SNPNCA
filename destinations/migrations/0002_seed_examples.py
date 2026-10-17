from django.db import migrations

# Example destinations so the page isn't empty; admins replace them with the real list.
EXAMPLES = [
    ("Paris", "Paris", "باريس", [
        ("Monter à la tour Eiffel au coucher du soleil", "Go up the Eiffel Tower at sunset", "صعود برج إيفل عند الغروب"),
        ("Visiter le musée du Louvre", "Visit the Louvre Museum", "زيارة متحف اللوفر"),
        ("Croisière sur la Seine", "Take a cruise on the Seine", "رحلة بحرية على نهر السين"),
        ("Se promener à Montmartre", "Stroll around Montmartre", "التجول في حي مونمارتر"),
    ]),
    ("Istanbul", "Istanbul", "إسطنبول", [
        ("Visiter Sainte-Sophie et la Mosquée bleue", "Visit Hagia Sophia and the Blue Mosque", "زيارة آيا صوفيا والمسجد الأزرق"),
        ("Flâner dans le Grand Bazar", "Wander through the Grand Bazaar", "التجول في السوق الكبير"),
        ("Croisière sur le Bosphore", "Take a Bosphorus cruise", "رحلة بحرية في مضيق البوسفور"),
        ("Goûter un vrai thé turc à Karaköy", "Have Turkish tea in Karaköy", "تذوق الشاي التركي في كاراكوي"),
    ]),
    ("Dubaï", "Dubai", "دبي", [
        ("Monter au sommet du Burj Khalifa", "Go to the top of the Burj Khalifa", "الصعود إلى قمة برج خليفة"),
        ("Safari dans le désert", "Go on a desert safari", "رحلة سفاري في الصحراء"),
        ("Voir le spectacle de la fontaine de Dubaï", "Watch the Dubai Fountain show", "مشاهدة عرض نافورة دبي"),
        ("Se promener dans le souk de l’or", "Walk through the Gold Souk", "التجول في سوق الذهب"),
    ]),
]


def seed(apps, schema_editor):
    Destination = apps.get_model("destinations", "Destination")
    if Destination.objects.exists():
        return
    for i, (fr, en, ar, activities) in enumerate(EXAMPLES):
        d = Destination.objects.create(name_fr=fr, name_en=en, name_ar=ar, position=i)
        for j, (a_fr, a_en, a_ar) in enumerate(activities):
            d.activities.create(text_fr=a_fr, text_en=a_en, text_ar=a_ar, position=j)


class Migration(migrations.Migration):
    dependencies = [("destinations", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
