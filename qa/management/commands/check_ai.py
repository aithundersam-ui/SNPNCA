"""`python manage.py check_ai` makes one small Claude call and says plainly why
the Q&A assistant would be unavailable. Never prints the API key."""

from django.conf import settings
from django.core.management.base import BaseCommand

from qa.llm import ClaudeClient, LLMError


class Command(BaseCommand):
    help = "Check that the Q&A assistant can reach the Claude API."

    def handle(self, *args, **options):
        key = settings.ANTHROPIC_API_KEY
        self.stdout.write(f"API key set: {'yes' if key else 'no'}" + (f" (starts with sk-ant-: {'yes' if key.startswith('sk-ant-') else 'NO'}, {len(key)} characters)" if key else ""))
        self.stdout.write(f"Model: {settings.CLAUDE_MODEL}")
        try:
            plan = ClaudeClient().plan("Combien de jours de congé annuel ?")
        except LLMError as exc:
            self.stdout.write(self.style.ERROR(f"Failed: {exc}"))
            return
        self.stdout.write(self.style.SUCCESS(f"OK. Claude answered (detected language: {plan.get('language')})."))
