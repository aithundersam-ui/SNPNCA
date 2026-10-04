from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Article


def visible_articles():
    return Article.objects.filter(is_published=True, published_at__lte=timezone.now())


@login_required
def article_list(request):
    page = Paginator(visible_articles().prefetch_related("images"), 10).get_page(request.GET.get("page"))
    return render(request, "news/list.html", {"page": page})


@login_required
def article_detail(request, pk):
    article = get_object_or_404(visible_articles().prefetch_related("images", "videos"), pk=pk)
    return render(request, "news/detail.html", {"article": article})
