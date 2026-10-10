"""
materials.views
================
Everything a student or Admin does with a Material, end to end:

    home              search box + faculty directory (also the site root)
    material_list     the browse/search/filter/paginate view — the one
                       place all of those query params are interpreted
    material_detail   metadata + preview for a single material
    material_download @login_required — logs a Download row, then
                       streams the file
    material_upload   @admin_required — create
    material_edit     @admin_required — update (same form/template as
                       upload; see materials/forms.py)
    material_delete   @admin_required — GET shows a confirmation page,
                       POST actually deletes (never delete on a bare GET)
    admin_dashboard   @admin_required — totals + recent activity

Permission model: every public view here is intentionally readable by
anyone (browsing the catalog isn't sensitive); `material_download` is
the one place we require login, because a Download row needs a student
to attribute to; the four Admin-only views use the
accounts.permissions.admin_required decorator rather than re-checking
`request.user.role` by hand in each view.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AcademicSession, Course, Faculty, Semester
from accounts.models import User
from accounts.permissions import admin_required

from .forms import MaterialUploadForm
from .models import Download, Material


def _safe_int(value):
    """
    request.GET values are always strings and never trustworthy —
    someone can put anything in a URL. Every numeric filter below
    (course/level/semester/session IDs) goes through this rather than
    straight into .filter(), so `?level=abc` or `?course=' OR '1'='1`
    quietly matches nothing instead of raising an uncaught ValueError
    (a 500 error) or reaching the ORM at all. The ORM itself already
    parameterizes every query — see SECURITY.md, "Parameterize queries"
    — so this isn't preventing SQL injection (that was never possible
    here); it's making bad input fail as a normal empty result instead
    of an application error.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def home(request):
    """Landing page: search bar + the faculty directory."""
    query = request.GET.get("q", "").strip()
    if query:
        return redirect(f"/materials/?q={query}")
    faculties = Faculty.objects.all()
    return render(request, "home.html", {"faculties": faculties})


def material_list(request):
    """
    Browse/search/filter materials — the core student flow.

    All filtering happens through GET params so the resulting URL is
    shareable and bookmarkable, and works with JavaScript disabled
    (each filter <select> in the template auto-submits its enclosing
    form via onchange, but a plain submit button works exactly the
    same). Recognized params, all optional and all combinable:

        q           free-text search (title, topic, description, course
                    code/title — see the Q() filter below)
        faculty     Faculty.slug
        department  Department.slug
        course      Course.id (set when arriving from a course page)
        level       Material.Level value, e.g. "200"
        semester    Semester.id
        session     AcademicSession.id
        file_type   e.g. "pdf" (derived from the stored file's extension)
        page        pagination, 20 materials per page
    """
    materials = Material.objects.select_related(
        "course",
        "course__department",
        "course__department__faculty",
        "semester",
        "session",
    )

    query = request.GET.get("q", "").strip()
    faculty = request.GET.get("faculty", "")
    department = request.GET.get("department", "")
    course_id = request.GET.get("course", "")
    level = request.GET.get("level", "")
    semester_id = request.GET.get("semester", "")
    session_id = request.GET.get("session", "")
    file_type = request.GET.get("file_type", "")

    if query:
        materials = materials.filter(
            Q(title__icontains=query)
            | Q(topic__icontains=query)
            | Q(description__icontains=query)
            | Q(course__code__icontains=query)
            | Q(course__title__icontains=query)
        )
    if faculty:
        materials = materials.filter(course__department__faculty__slug=faculty)
    if department:
        materials = materials.filter(course__department__slug=department)

    course_id_int = _safe_int(course_id)
    if course_id_int is not None:
        materials = materials.filter(course_id=course_id_int)
    level_int = _safe_int(level)
    if level_int is not None:
        materials = materials.filter(level=level_int)
    semester_id_int = _safe_int(semester_id)
    if semester_id_int is not None:
        materials = materials.filter(semester_id=semester_id_int)
    session_id_int = _safe_int(session_id)
    if session_id_int is not None:
        materials = materials.filter(session_id=session_id_int)
    if file_type:
        materials = materials.filter(file_type=file_type)

    paginator = Paginator(materials, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Used by pagination links in the template so "next page" doesn't
    # silently drop whichever filters are currently applied.
    querydict = request.GET.copy()
    querydict.pop("page", None)
    base_query = querydict.urlencode()

    bookmarked_ids = set()
    if request.user.is_authenticated:
        bookmarked_ids = set(request.user.bookmarks.values_list("material_id", flat=True))

    context = {
        "page_obj": page_obj,
        "base_query": base_query,
        "query": query,
        "bookmarked_ids": bookmarked_ids,
        "faculties": Faculty.objects.all(),
        "semesters": Semester.objects.all(),
        "sessions": AcademicSession.objects.all(),
        "levels": Material.Level.choices,
        "file_types": (
            Material.objects.exclude(file_type="").values_list("file_type", flat=True).distinct().order_by("file_type")
        ),
        "selected": {
            "faculty": faculty,
            "department": department,
            "course": course_id,
            "level": level,
            "semester": semester_id,
            "session": session_id,
            "file_type": file_type,
        },
    }
    return render(request, "materials/material_list.html", context)


def material_detail(request, pk):
    """Metadata + inline preview (PDFs only, for now) for one material."""
    material = get_object_or_404(
        Material.objects.select_related("course", "course__department__faculty", "semester", "session"),
        pk=pk,
    )
    is_bookmarked = (
        request.user.is_authenticated and material.bookmarked_by.filter(student=request.user).exists()
    )
    return render(
        request,
        "materials/material_detail.html",
        {"material": material, "is_bookmarked": is_bookmarked},
    )


@login_required
def material_download(request, pk):
    """Log the download for stats, then stream the file to the student."""
    material = get_object_or_404(Material, pk=pk)
    if not material.file:
        raise Http404("This material has no file attached.")

    Download.objects.create(material=material, student=request.user)

    try:
        file_handle = material.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("The file could not be found in storage.") from exc

    filename = material.file.name.rsplit("/", 1)[-1]
    return FileResponse(file_handle, as_attachment=True, filename=filename)


@admin_required
def material_upload(request):
    """Admin-only create form. See material_edit for the update counterpart."""
    if request.method == "POST":
        form = MaterialUploadForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.uploaded_by = request.user
            material.save()
            messages.success(request, f"“{material.title}” was uploaded.")
            return redirect("materials:material_detail", pk=material.pk)
    else:
        form = MaterialUploadForm()
    return render(request, "materials/material_form.html", {"form": form, "mode": "upload"})


@admin_required
def material_edit(request, pk):
    """
    Admin-only update form. Reuses MaterialUploadForm and
    material_form.html (mode="edit" swaps a couple of labels and skips
    re-requiring the file field) rather than duplicating the form.
    """
    material = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        form = MaterialUploadForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, f"“{material.title}” was updated.")
            return redirect("materials:material_detail", pk=material.pk)
    else:
        form = MaterialUploadForm(instance=material)
    return render(request, "materials/material_form.html", {"form": form, "mode": "edit", "material": material})


@admin_required
def material_delete(request, pk):
    """
    Admin-only delete. GET renders a confirmation page; only POST
    actually deletes — this view never mutates state on a GET request,
    so a crawler, browser prefetch, or accidental link click can't
    delete a material.
    """
    material = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        title = material.title
        material.file.delete(save=False)
        material.delete()
        messages.success(request, f"“{title}” was deleted.")
        return redirect("materials:material_list")
    return render(request, "materials/material_confirm_delete.html", {"material": material})


@admin_required
def admin_dashboard(request):
    """Summary counts + the 8 most recent uploads/downloads, for a quick daily check-in."""
    context = {
        "total_students": User.objects.filter(role=User.Role.STUDENT).count(),
        "total_courses": Course.objects.count(),
        "total_materials": Material.objects.count(),
        "total_downloads": Download.objects.count(),
        "recent_materials": Material.objects.select_related("course")[:8],
        "recent_downloads": Download.objects.select_related("material", "student")[:8],
    }
    return render(request, "materials/admin_dashboard.html", context)
