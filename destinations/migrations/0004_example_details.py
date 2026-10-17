from urllib.parse import quote_plus

from django.db import migrations

# Descriptions and map links for the example activities from 0002 (only if still unchanged).
DETAILS = {
    "Monter à la tour Eiffel au coucher du soleil": (
        "Eiffel Tower, Paris",
        "Montez au 2e étage ou au sommet pour voir Paris s’illuminer. Réservez en ligne pour éviter la file.",
        "Go up to the 2nd floor or the top to watch Paris light up. Book online to skip the queue.",
        "اصعد إلى الطابق الثاني أو إلى القمة لمشاهدة باريس وهي تتلألأ. احجز عبر الإنترنت لتفادي الطابور.",
    ),
    "Visiter le musée du Louvre": (
        "Musée du Louvre, Paris",
        "La Joconde, la Vénus de Milo et des milliers d’œuvres. Gratuit le premier vendredi soir du mois.",
        "The Mona Lisa, the Venus de Milo and thousands of works. Free on the first Friday evening of the month.",
        "الموناليزا وفينوس دي ميلو وآلاف الأعمال الفنية. الدخول مجاني مساء أول جمعة من كل شهر.",
    ),
    "Croisière sur la Seine": (
        "Bateaux Mouches, Paris",
        "Une heure sur l’eau pour voir les monuments de Paris sans marcher, idéale après un vol.",
        "One hour on the water to see Paris's landmarks without walking, perfect after a flight.",
        "ساعة على الماء لمشاهدة معالم باريس دون مشي، مثالية بعد رحلة طيران.",
    ),
    "Se promener à Montmartre": (
        "Sacré-Cœur, Montmartre, Paris",
        "Ruelles pavées, peintres de la place du Tertre et vue sur tout Paris depuis le Sacré-Cœur.",
        "Cobbled lanes, the painters of Place du Tertre and a view over all of Paris from the Sacré-Cœur.",
        "أزقة مرصوفة ورسامو ساحة تيرتر وإطلالة على باريس كلها من كنيسة القلب المقدس.",
    ),
    "Visiter Sainte-Sophie et la Mosquée bleue": (
        "Hagia Sophia, Istanbul",
        "Les deux monuments se font face à Sultanahmet. Prévoyez une tenue couvrante.",
        "The two landmarks face each other in Sultanahmet. Wear clothes that cover shoulders and knees.",
        "يتقابل المعلمان في حي السلطان أحمد. يُرجى ارتداء ملابس محتشمة.",
    ),
    "Flâner dans le Grand Bazar": (
        "Grand Bazaar, Istanbul",
        "Plus de 4 000 boutiques couvertes. Négociez les prix, c’est l’usage. Fermé le dimanche.",
        "Over 4,000 covered shops. Haggling is expected. Closed on Sundays.",
        "أكثر من 4000 متجر مسقوف. المساومة على الأسعار أمر معتاد. مغلق يوم الأحد.",
    ),
    "Croisière sur le Bosphore": (
        "Eminönü ferry pier, Istanbul",
        "Prenez le ferry public depuis Eminönü pour longer l’Europe et l’Asie à petit prix.",
        "Take the public ferry from Eminönü to sail between Europe and Asia for very little.",
        "استقل العبّارة العامة من إمينونو للإبحار بين أوروبا وآسيا بسعر زهيد.",
    ),
    "Goûter un vrai thé turc à Karaköy": (
        "Karaköy, Istanbul",
        "Quartier branché au bord de l’eau, avec cafés, baklava et vue sur la Corne d’Or.",
        "A trendy waterfront district with cafés, baklava and views of the Golden Horn.",
        "حي عصري على الواجهة البحرية بمقاهيه وحلوى البقلاوة وإطلالته على القرن الذهبي.",
    ),
    "Monter au sommet du Burj Khalifa": (
        "Burj Khalifa, Dubai",
        "La plus haute tour du monde. Le créneau du coucher du soleil est le plus beau, réservez tôt.",
        "The tallest building in the world. The sunset slot is the best, so book early.",
        "أطول برج في العالم. موعد الغروب هو الأجمل، لذا احجز مبكرًا.",
    ),
    "Safari dans le désert": (
        "Dubai Desert Conservation Reserve",
        "Dunes en 4x4, coucher de soleil et dîner sous les étoiles. Prise en charge à l’hôtel.",
        "Dune bashing, sunset and dinner under the stars, with hotel pick-up.",
        "قيادة على الكثبان الرملية وغروب الشمس وعشاء تحت النجوم، مع النقل من الفندق.",
    ),
    "Voir le spectacle de la fontaine de Dubaï": (
        "The Dubai Fountain",
        "Gratuit, toutes les 30 minutes le soir, au pied du Burj Khalifa.",
        "Free, every 30 minutes in the evening, at the foot of the Burj Khalifa.",
        "مجاني، كل 30 دقيقة مساءً، عند سفح برج خليفة.",
    ),
    "Se promener dans le souk de l’or": (
        "Gold Souk, Deira, Dubai",
        "Des centaines de bijouteries à Deira. Traversez la crique en abra pour y aller.",
        "Hundreds of jewellers in Deira. Cross the creek by abra boat to get there.",
        "مئات من محلات المجوهرات في ديرة. اعبر الخور بقارب العبرة للوصول إليه.",
    ),
}


def fill(apps, schema_editor):
    Activity = apps.get_model("destinations", "Activity")
    for activity in Activity.objects.filter(title_fr__in=DETAILS, description_fr="", maps_url=""):
        place, fr, en, ar = DETAILS[activity.title_fr]
        activity.description_fr, activity.description_en, activity.description_ar = fr, en, ar
        activity.maps_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(place)
        activity.save()


class Migration(migrations.Migration):
    dependencies = [("destinations", "0003_activity_details")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
