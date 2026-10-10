"""
bookmarks.views
================
Two views: a POST-only toggle (add if missing, remove if present — see
Bookmark's unique_together for why this is race-safe) and a plain list
of the current student's bookmarks.

toggle_bookmark is deliberately POST-only (@require_POST): bookmarking
changes state, so — same reasoning as material_delete requiring POST —
it must not be triggerable by a GET link, browser prefetch, or crawler.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from materials.models import Material

from .models import Bookmark


@login_required
@require_POST
def toggle_bookmark(request, pk):
    """
    Add a bookmark if the student doesn't have one for this material yet,
    otherwise remove it. `next` (a hidden field in the surrounding form,
    set to `request.path` in the templates that use it) sends the
    student back to whichever page they clicked the button from, so the
    same view works from the detail page, the browse list, and the
    bookmarks list itself.
    """
    material = get_object_or_404(Material, pk=pk)
    bookmark, created = Bookmark.objects.get_or_create(student=request.user, material=material)
    if created:
        messages.success(request, "Added to your bookmarks.")
    else:
        bookmark.delete()
        messages.info(request, "Removed from your bookmarks.")

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("materials:material_detail", pk=pk)


@login_required
def bookmark_list(request):
    """The signed-in student's own bookmarks — never another student's."""
    bookmarks = request.user.bookmarks.select_related("material", "material__course")
    return render(request, "bookmarks/bookmark_list.html", {"bookmarks": bookmarks})
