"""Downloads the free Argos Translate models used for automatic translation
(French <-> English and English <-> Arabic, about 100 MB each) and runs one
test sentence through each, so nothing is downloaded later while an admin waits."""

from django.core.management.base import BaseCommand, CommandError

PAIRS = [("fr", "en"), ("en", "fr"), ("en", "ar"), ("ar", "en")]
SAMPLES = {"fr": "Bonjour à tous les adhérents.", "en": "Hello to all members.", "ar": "مرحبا بجميع المنخرطين."}


class Command(BaseCommand):
    help = "Install the offline translation models (Argos Translate)."

    def handle(self, *args, **options):
        try:
            from argostranslate import package, translate
        except ImportError as exc:
            raise CommandError("Argos Translate is not installed: pip install -r requirements-translate.txt") from exc

        installed = {(p.from_code, p.to_code) for p in package.get_installed_packages()}
        missing = [pair for pair in PAIRS if pair not in installed]
        if missing:
            self.stdout.write("Downloading the model list...")
            package.update_package_index()
            available = {(p.from_code, p.to_code): p for p in package.get_available_packages()}
            for pair in missing:
                if pair not in available:
                    raise CommandError("No Argos model for %s -> %s" % pair)
                self.stdout.write("Installing %s -> %s..." % pair)
                package.install_from_path(available[pair].download())

        for source, target in PAIRS + [("fr", "ar"), ("ar", "fr")]:
            text = translate.translate(SAMPLES[source], source, target)
            self.stdout.write("%s -> %s: %s" % (source, target, text))
        self.stdout.write(self.style.SUCCESS("Translation models ready."))
