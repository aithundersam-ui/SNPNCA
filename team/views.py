import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import TeamMember


def team_page(request):
    people = list(TeamMember.objects.all())
    R = TeamMember.Role
    return render(
        request,
        "team/page.html",
        {
            "leaders": [p for p in people if p.role in (R.PRESIDENT, R.SECRETARY_GENERAL)],
            "officers": [p for p in people if p.role == R.TREASURER],
            "members": [p for p in people if p.role == R.MEMBER],
        },
    )


def photo(request, pk):
    """Team photos are public, like the page itself."""
    person = get_object_or_404(TeamMember, pk=pk)
    if not person.photo or not person.photo.storage.exists(person.photo.name):
        raise Http404
    content_type, _enc = mimetypes.guess_type(person.photo.name)
    response = FileResponse(person.photo.open("rb"), content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=86400"
    return response
