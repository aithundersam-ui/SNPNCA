from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import Activity, Destination


@login_required
def destination_list(request):
    return render(request, "destinations/list.html", {"destinations": Destination.objects.all()})


@login_required
def destination_detail(request, pk):
    destination = get_object_or_404(Destination.objects.prefetch_related("activities"), pk=pk)
    return render(request, "destinations/detail.html", {"destination": destination})


def _photo_response(obj):
    if not obj.photo or not obj.photo.storage.exists(obj.photo.name):
        raise Http404
    response = FileResponse(obj.photo.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response


@login_required
def photo(request, pk):
    return _photo_response(get_object_or_404(Destination, pk=pk))


@login_required
def activity_photo(request, pk):
    return _photo_response(get_object_or_404(Activity, pk=pk))
