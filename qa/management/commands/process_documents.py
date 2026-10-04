import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from qa.processing import run_once


class Command(BaseCommand):
    help = "Background worker: extract, OCR and index uploaded PDFs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process everything waiting, then exit.")
        parser.add_argument("--interval", type=float, default=5.0)

    def handle(self, *args, once=False, interval=5.0, **options):
        self.stdout.write("Document worker started.")
        while True:
            close_old_connections()
            worked = run_once()
            if not worked:
                if once:
                    return
                time.sleep(interval)
