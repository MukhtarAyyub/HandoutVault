"""
exams.views
===========
Everything a student or Admin does with exam-preparation content, written
ONCE for both kinds (past questions and summaries). Each view receives the
`kind` URL segment and resolves it through exams.kinds, so
/exam-prep/past-questions/... and /exam-prep/summaries/... share one
implementation.

Access rules
------------
* Everything under /exam-prep/ requires a login. An anonymous visitor who
  taps "Exam Preparation" is sent to the login page first and brought
  straight back afterwards (Django's `?next=` handling in @login_required).
* Add / edit / delete are Admin-only (@admin_required) — students can read
  and download, never upload.
"""
from itertools import chain

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AcademicSession, Course, Department, Faculty, Semester
from accounts.permissions import admin_required
from materials.models import Material

from .kinds import KINDS, get_kind_or_404
from .utils import course_resource_counts

PAGE_SIZE = 20

# Joins every list/detail page needs, so rendering N rows costs one query, not N+1.
_BASE_JOINS = ("course", "course__department", "course__department__faculty", "semester", "session")


def _int_or_none(value):
    """
    Query-string values are strings and never trustworthy. `?course=abc`
    should behave like no course filter, not raise a ValueError (a 500).
    (The ORM already parameterizes every query, so this is about robustness,
    not SQL injection — same reasoning as materials.views._safe_int.)
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@login_required
def hub(request):
    """Landing page for Exam Preparation: one card per kind, plus what's newest."""
    sections = [{"kind": kind, "count": kind.model.objects.count()} for kind in KINDS.values()]
    newest_per_kind = (
        kind.model.objects.select_related("course", "semester", "session")[:6] for kind in KINDS.values()
    )
    recent = sorted(chain(*newest_per_kind), key=lambda item: item.upload_date, reverse=True)[:6]
    return render(request, "exams/hub.html", {"sections": sections, "recent": recent})


@login_required
def resource_list(request, kind):
    """
    Browse/search/filter one kind of exam content. Filters arrive as GET
    params so a filtered view is a plain, shareable URL (and works without
    JavaScript). All optional, all combinable:

        q           free text: title, description, course code/title
                    (plus the handout title, for summaries)
        faculty     Faculty id          department  Department id
        course      Course id           level       e.g. 200
        semester    Semester id         session     AcademicSession id
        page        20 items per page
    """
    cfg = get_kind_or_404(kind)
    items = cfg.model.objects.select_related(*_BASE_JOINS, *cfg.extra_select_related)

    q = request.GET.get("q", "").strip()
    selected = {
        name: _int_or_none(request.GET.get(name))
        for name in ("faculty", "department", "course", "level", "semester", "session")
    }

    if q:
        search = Q()
        for field in ("title", "description", "course__code", "course__title", *cfg.extra_search_fields):
            search |= Q(**{f"{field}__icontains": q})
        items = items.filter(search)
    if selected["faculty"] is not None:
        items = items.filter(course__department__faculty_id=selected["faculty"])
    if selected["department"] is not None:
        items = items.filter(course__department_id=selected["department"])
    if selected["course"] is not None:
        items = items.filter(course_id=selected["course"])
    if selected["level"] is not None:
        items = items.filter(level=selected["level"])
    if selected["semester"] is not None:
        items = items.filter(semester_id=selected["semester"])
    if selected["session"] is not None:
        items = items.filter(session_id=selected["session"])

    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))

    # Filtered to one course? Show its name and the Handouts | Past questions | Summaries switcher.
    course_obj = None
    if selected["course"] is not None:
        course_obj = Course.objects.select_related("department", "department__faculty").filter(
            pk=selected["course"]
        ).first()

    # Pagination links must carry the active filters along.
    querydict = request.GET.copy()
    querydict.pop("page", None)

    context = {
        "cfg": cfg,
        "page_obj": page_obj,
        "q": q,
        "selected": selected,
        "course_obj": course_obj,
        "filter_count": sum(1 for value in selected.values() if value is not None),
        "course_counts": course_resource_counts(course_obj) if course_obj else None,
        "has_filters": bool(q) or any(value is not None for value in selected.values()),
        "base_query": querydict.urlencode(),
        # Dropdown options, ordered so the template can group them with {% regroup %}.
        "faculties": Faculty.objects.all(),
        "departments": Department.objects.select_related("faculty").order_by("faculty__name", "name"),
        "courses": Course.objects.select_related("department").order_by("department__name", "code"),
        "levels": Material.Level.choices,
        "semesters": Semester.objects.all(),
        "sessions": AcademicSession.objects.all(),
    }
    return render(request, "exams/list.html", context)


@login_required
def resource_detail(request, kind, pk):
    """Metadata + inline preview (PDFs) for one past question or summary."""
    cfg = get_kind_or_404(kind)
    obj = get_object_or_404(
        cfg.model.objects.select_related(*_BASE_JOINS, *cfg.extra_select_related), pk=pk
    )
    return render(request, "exams/detail.html", {"cfg": cfg, "obj": obj})


@login_required
def resource_download(request, kind, pk):
    """Stream the file as an attachment, then count it."""
    cfg = get_kind_or_404(kind)
    obj = get_object_or_404(cfg.model, pk=pk)
    if not obj.file:
        raise Http404("This item has no file attached.")
    try:
        handle = obj.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("The file could not be found in storage.") from exc

    # F() makes the +1 happen inside the database, so two students downloading
    # at the same moment can't overwrite each other's count.
    cfg.model.objects.filter(pk=obj.pk).update(download_count=F("download_count") + 1)
    return FileResponse(handle, as_attachment=True, filename=obj.filename)


def _initial_from_handout(request, cfg):
    """
    /exam-prep/summaries/add/?handout=<id> (the "Add a summary" button on a
    handout's page) pre-fills the form from that handout, so the Admin only
    has to write the title and attach the file.
    """
    if "handout" not in cfg.form.base_fields:
        return {}
    handout_id = _int_or_none(request.GET.get("handout"))
    handout = Material.objects.select_related("course").filter(pk=handout_id).first() if handout_id else None
    if handout is None:
        return {}
    return {
        "handout": handout,
        "course": handout.course,
        "level": handout.level,
        "semester": handout.semester,
        "session": handout.session,
        "title": f"Summary: {handout.title}",
    }


@admin_required
def resource_add(request, kind):
    """Admin-only create form. See resource_edit for the update counterpart."""
    cfg = get_kind_or_404(kind)
    if request.method == "POST":
        form = cfg.form(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.uploaded_by = request.user
            obj.save()
            messages.success(request, f"“{obj.title}” was added to {cfg.label_plural.lower()}.")
            return redirect(obj)
    else:
        form = cfg.form(initial=_initial_from_handout(request, cfg))
    return render(request, "exams/form.html", {"cfg": cfg, "form": form, "mode": "add"})


@admin_required
def resource_edit(request, kind, pk):
    """Admin-only update. Same form and template as resource_add."""
    cfg = get_kind_or_404(kind)
    obj = get_object_or_404(cfg.model, pk=pk)
    if request.method == "POST":
        form = cfg.form(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"“{obj.title}” was updated.")
            return redirect(obj)
    else:
        form = cfg.form(instance=obj)
    return render(request, "exams/form.html", {"cfg": cfg, "form": form, "mode": "edit", "obj": obj})


@admin_required
def resource_delete(request, kind, pk):
    """GET shows a confirmation page; only POST deletes (never mutate on a GET)."""
    cfg = get_kind_or_404(kind)
    obj = get_object_or_404(cfg.model, pk=pk)
    if request.method == "POST":
        title = obj.title
        obj.file.delete(save=False)
        obj.delete()
        messages.success(request, f"“{title}” was deleted.")
        return redirect("exams:list", kind=cfg.slug)
    return render(request, "exams/confirm_delete.html", {"cfg": cfg, "obj": obj})
