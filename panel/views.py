import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts import csv_import
from accounts import lockout
from accounts import permissions as perms
from accounts.audit import log_action
from accounts.emails import send_invitation, send_templated
from accounts.forms import CsvUploadForm, UserForm
from accounts.models import AuditLog, Role, User
from core.forms import ReplyForm, SiteContentForm
from core.models import ContactMessage, ContactReply, SiteContent
from news.models import Article, ArticleImage, ArticleVideo
from qa.models import Document

from .forms import ArticleForm, DocumentUploadForm, RoleForm

logger = logging.getLogger(__name__)
admin_required = perms.admin_required
master_required = perms.master_required

CSV_SESSION_KEY = "csv_import_rows"


def _invite(request, user):
    try:
        send_invitation(user)
        return True
    except Exception:
        logger.exception("Invitation email failed for %s", user.email)
        messages.warning(request, _("The account was created but the invitation email could not be sent to %(email)s.") % {"email": user.email})
        return False


@admin_required
def dashboard(request):
    return render(
        request,
        "panel/dashboard.html",
        {
            "user_count": User.objects.count(),
            "new_messages": ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count(),
            "documents": Document.objects.count(),
            "documents_pending": Document.objects.filter(status__in=[Document.Status.PENDING, Document.Status.PROCESSING]).count(),
            "articles": Article.objects.count(),
        },
    )


# ---------------------------------------------------------------- Users


@admin_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    users = User.objects.all()
    if q:
        users = users.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
    page = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(request, "panel/users.html", {"page": page, "q": q})


@admin_required
def user_create(request, role=Role.USER):
    if role != Role.USER and not request.user.is_master:
        raise PermissionDenied
    form = UserForm(request.POST or None, actor=request.user, initial={"role": role})
    if request.method == "POST" and form.is_valid():
        new_role = form.cleaned_data.get("role", Role.USER)
        if not perms.can_assign_role(request.user, new_role):
            raise PermissionDenied
        user = form.save(commit=False)
        user.role = new_role
        user.set_unusable_password()
        user.save()
        log_action(request, "user.create", user.email, role=user.role)
        if _invite(request, user):
            messages.success(request, _("Account created. A set-password link was emailed to %(email)s.") % {"email": user.email})
        return redirect("panel:users")
    return render(request, "panel/user_form.html", {"form": form, "creating": True})


@admin_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not perms.can_manage(request.user, target):
        raise PermissionDenied
    old_role, old_active = target.role, target.is_active
    form = UserForm(request.POST or None, instance=target, actor=request.user)
    if request.method == "POST" and form.is_valid():
        new_role = form.cleaned_data.get("role", old_role)
        new_active = form.cleaned_data["is_active"]
        user = form.save(commit=False)
        # Role and active state go through the guarded helpers, never straight from the form.
        user.role, user.is_active = old_role, old_active
        try:
            with transaction.atomic():
                user.save()
                if new_role != old_role:
                    perms.change_role(request.user, user, new_role)
                    log_action(request, "user.role_change", user.email, old=old_role, new=new_role)
                if new_active != old_active:
                    perms.set_active(request.user, user, new_active)
                    log_action(request, "user.activate" if new_active else "user.deactivate", user.email)
        except perms.LastMasterAdminError:
            messages.error(request, _("There must always be at least one active Master Admin."))
            return redirect("panel:user_edit", pk=pk)
        log_action(request, "user.update", user.email)
        messages.success(request, _("Changes saved."))
        return redirect("panel:users")
    return render(request, "panel/user_form.html", {"form": form, "target": target})


@master_required
def user_set_password(request, pk):
    """Master Admins can set any account's password. The password is never
    emailed, shown again or written to the audit log."""
    target = get_object_or_404(User, pk=pk)
    form = SetPasswordForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()  # also signs the person out of their other sessions
        if target.pk == request.user.pk:
            update_session_auth_hash(request, target)
        lockout.clear(target.email)
        log_action(request, "user.password_set", target.email)
        messages.success(request, _("Password changed for %(email)s.") % {"email": target.email})
        return redirect("panel:admins" if target.is_admin else "panel:users")
    return render(request, "panel/set_password.html", {"form": form, "target": target})


@admin_required
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not perms.can_manage(request.user, target):
        raise PermissionDenied
    if request.method == "POST":
        email = target.email
        try:
            perms.delete_user(request.user, target)
        except perms.LastMasterAdminError:
            messages.error(request, _("There must always be at least one active Master Admin."))
            return redirect("panel:users")
        log_action(request, "user.delete", email)
        messages.success(request, _("The account was deleted."))
        if target.pk == request.user.pk:
            return redirect("core:home")
        return redirect("panel:users")
    return render(request, "panel/confirm_delete.html", {"object_label": str(target), "cancel_url": "panel:users"})


@admin_required
@require_POST
def user_resend_invite(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not perms.can_manage(request.user, target):
        raise PermissionDenied
    if _invite(request, target):
        log_action(request, "user.invite_resent", target.email)
        messages.success(request, _("A new set-password link was emailed to %(email)s.") % {"email": target.email})
    return redirect("panel:users")


# ---------------------------------------------------------------- CSV import


@admin_required
def csv_template(request):
    response = HttpResponse(csv_import.TEMPLATE_CSV.encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="snpnca_members_template.csv"'
    return response


@admin_required
def csv_upload(request):
    form = CsvUploadForm(request.POST or None, request.FILES or None)
    rows = None
    if request.method == "POST" and form.is_valid():
        try:
            text = csv_import.decode(form.cleaned_data["file"].read())
            rows = csv_import.parse(text, request.user)
        except csv_import.CsvFormatError as exc:
            form.add_error("file", str(exc))
        else:
            request.session[CSV_SESSION_KEY] = [r.as_dict() for r in rows if r.ok]
    ready = sum(1 for r in rows if r.ok) if rows else 0
    return render(request, "panel/csv_import.html", {"form": form, "rows": rows, "ready": ready})


@admin_required
@require_POST
def csv_apply(request):
    rows = request.session.pop(CSV_SESSION_KEY, None)
    if not rows:
        messages.error(request, _("Nothing to import. Please upload the file again."))
        return redirect("panel:csv_upload")
    created = csv_import.apply(rows, request.user)
    failed = 0
    for user in created:
        try:
            send_invitation(user)
        except Exception:
            failed += 1
            logger.exception("Invitation email failed for %s", user.email)
    log_action(request, "user.csv_import", f"{len(created)} accounts", emails=[u.email for u in created][:500])
    messages.success(request, _("%(count)s accounts created and invited.") % {"count": len(created)})
    if failed:
        messages.warning(request, _("%(count)s invitation emails could not be sent. Use “Resend invitation” on those accounts.") % {"count": failed})
    return redirect("panel:users")


# ---------------------------------------------------------------- Admins (Master Admin only)


@master_required
def admin_list(request):
    admins = User.objects.filter(role__in=[Role.ADMIN, Role.MASTER])
    return render(request, "panel/admins.html", {"admins": admins, "role_form": RoleForm()})


@master_required
@require_POST
def change_role(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = RoleForm(request.POST)
    if form.is_valid():
        old = target.role
        try:
            perms.change_role(request.user, target, form.cleaned_data["role"])
        except perms.LastMasterAdminError:
            messages.error(request, _("There must always be at least one active Master Admin."))
        else:
            log_action(request, "user.role_change", target.email, old=old, new=target.role)
            messages.success(request, _("Role updated."))
    return redirect("panel:admins")


# ---------------------------------------------------------------- Documents


@admin_required
def document_list(request):
    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["file"]
        doc = Document(
            title=form.cleaned_data["title"] or Path(f.name).stem.replace("_", " ")[:255],
            original_filename=Path(f.name).name[:255],
            size_bytes=f.size,
            page_count=form.page_count,
            uploaded_by=request.user,
        )
        doc.file.save("upload.pdf", f, save=False)
        doc.save()
        log_action(request, "document.upload", doc.title, filename=doc.original_filename, size=doc.size_bytes)
        messages.success(request, _("The PDF was uploaded and is being processed."))
        return redirect("panel:documents")
    documents = Document.objects.all().order_by("-created_at")
    return render(request, "panel/documents.html", {"form": form, "documents": documents, "max_mb": settings.MAX_PDF_MB})


@admin_required
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method == "POST":
        title = doc.title
        doc.delete()
        log_action(request, "document.delete", title)
        messages.success(request, _("The document and its extracted text were deleted."))
        return redirect("panel:documents")
    return render(request, "panel/confirm_delete.html", {"object_label": doc.title, "cancel_url": "panel:documents"})


@admin_required
@require_POST
def document_retry(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    doc.status = Document.Status.PENDING
    doc.error = ""
    doc.save(update_fields=["status", "error"])
    log_action(request, "document.reprocess", doc.title)
    return redirect("panel:documents")


# ---------------------------------------------------------------- News


@admin_required
def news_list(request):
    page = Paginator(Article.objects.all(), 25).get_page(request.GET.get("page"))
    return render(request, "panel/news.html", {"page": page})


@admin_required
def news_edit(request, pk=None):
    article = get_object_or_404(Article, pk=pk) if pk else Article(created_by=request.user)
    form = ArticleForm(request.POST or None, request.FILES or None, instance=article)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            article = form.save()
            article.videos.all().delete()
            ArticleVideo.objects.bulk_create(
                [ArticleVideo(article=article, url=u, position=i) for i, u in enumerate(form.cleaned_data["video_urls"])]
            )
            start = article.images.count()
            for i, f in enumerate(form.cleaned_data["new_images"]):
                ArticleImage.objects.create(article=article, image=f, position=start + i)
            remove = request.POST.getlist("remove_image")
            for img in article.images.filter(pk__in=[r for r in remove if r.isdigit()]):
                img.delete()
        log_action(request, "news.update" if pk else "news.create", str(article))
        messages.success(request, _("Article saved."))
        return redirect("panel:news")
    return render(request, "panel/news_form.html", {"form": form, "article": article})


@admin_required
def news_delete(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST":
        label = str(article)
        for img in article.images.all():
            img.delete()
        article.delete()
        log_action(request, "news.delete", label)
        messages.success(request, _("Article deleted."))
        return redirect("panel:news")
    return render(request, "panel/confirm_delete.html", {"object_label": str(article), "cancel_url": "panel:news"})


# ---------------------------------------------------------------- Contact messages


@admin_required
def message_list(request):
    status = request.GET.get("status", "")
    qs = ContactMessage.objects.all()
    if status in ContactMessage.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "panel/messages.html", {"page": page, "status": status})


@admin_required
def message_detail(request, pk):
    contact = get_object_or_404(ContactMessage, pk=pk)
    form = ReplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        body = form.cleaned_data["body"]
        try:
            send_templated(contact.email, "contact_reply", {"contact": contact, "body": body}, contact.language)
        except Exception:
            logger.exception("Reply email failed")
            messages.error(request, _("The email could not be sent. Please try again later."))
        else:
            ContactReply.objects.create(contact=contact, body=body, sent_by=request.user)
            contact.status = ContactMessage.Status.REPLIED
            contact.save(update_fields=["status"])
            log_action(request, "contact.reply", contact.email, message_id=contact.pk)
            messages.success(request, _("Your reply was sent."))
            return redirect("panel:message_detail", pk=pk)
    return render(request, "panel/message_detail.html", {"contact": contact, "form": form})


@admin_required
def message_delete(request, pk):
    contact = get_object_or_404(ContactMessage, pk=pk)
    if request.method == "POST":
        contact.delete()
        log_action(request, "contact.delete", contact.email)
        messages.success(request, _("Message deleted."))
        return redirect("panel:messages")
    return render(request, "panel/confirm_delete.html", {"object_label": str(contact), "cancel_url": "panel:messages"})


# ---------------------------------------------------------------- Home page content and audit log


@admin_required
def home_content(request):
    form = SiteContentForm(request.POST or None, instance=SiteContent.load())
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "home.update")
        messages.success(request, _("Home page updated."))
        return redirect("panel:home_content")
    return render(request, "panel/home_content.html", {"form": form})


@admin_required
def audit_log(request):
    page = Paginator(AuditLog.objects.all(), 50).get_page(request.GET.get("page"))
    return render(request, "panel/audit.html", {"page": page})
