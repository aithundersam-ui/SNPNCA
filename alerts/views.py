from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Alert


@login_required
def alert_list(request):
    return render(request, "alerts/list.html", {"alerts": Alert.objects.all()[:50]})


@login_required
def alert_detail(request, pk):
    return render(request, "alerts/detail.html", {"alert": get_object_or_404(Alert, pk=pk)})
