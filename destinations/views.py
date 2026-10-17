from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import Destination


@login_required
def destination_list(request):
    destinations = Destination.objects.prefetch_related("activities")
    return render(request, "destinations/list.html", {"destinations": destinations})


@login_required
def photo(request, pk):
    destination = get_object_or_404(Destination, pk=pk)
    if not destination.photo or not destination.photo.storage.exists(destination.photo.name):
        raise Http404
    response = FileResponse(destination.photo.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response
