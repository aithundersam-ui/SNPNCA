from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from accounts.lockout import hit_rate_limit

from . import assistant
from .models import Document, QAMessage


class QuestionForm(forms.Form):
    question = forms.CharField(
        label=gettext_lazy("Your question"),
        min_length=3,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 1, "placeholder": gettext_lazy("Ask about your documents ...")}),
    )


@login_required
def chat(request):
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if hit_rate_limit(f"qa:{request.user.pk}", settings.QA_RATE_LIMIT, 600):
            messages.error(request, _("You have asked many questions in a short time. Please wait a few minutes."))
            return redirect("qa:chat")
        question = form.cleaned_data["question"]
        QAMessage.objects.create(user=request.user, role=QAMessage.Role.USER, content=question)
        result = assistant.ask(question, ui_language=translation.get_language()[:2])
        QAMessage.objects.create(
            user=request.user,
            role=QAMessage.Role.ASSISTANT,
            content=result.text,
            citations=result.citations,
            answered=result.answered,
        )
        return redirect(f"{request.path}#latest")

    history = list(QAMessage.objects.filter(user=request.user).order_by("-created_at", "-pk")[:40])[::-1]
    documents = Document.objects.filter(status=Document.Status.READY)
    return render(request, "qa/chat.html", {"form": form, "history": history, "documents": documents})


@login_required
@require_POST
def clear(request):
    QAMessage.objects.filter(user=request.user).delete()
    return redirect("qa:chat")


@login_required
def document_list(request):
    documents = Document.objects.filter(status=Document.Status.READY).order_by("-created_at")
    return render(request, "qa/documents.html", {"documents": documents})


@login_required
def document_file(request, pk):
    """Members can open a cited PDF. Served through Django, never from a public URL."""
    document = get_object_or_404(Document, pk=pk, status=Document.Status.READY)
    try:
        handle = document.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(handle, content_type="application/pdf", filename=document.original_filename)
    response["Cache-Control"] = "private, no-store"
    return response
