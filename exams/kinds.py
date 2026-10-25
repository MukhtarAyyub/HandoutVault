"""
exams.kinds
===========
The one place that knows which kinds of exam-preparation content exist.

Past questions and summaries behave almost identically (list, detail,
download, add, edit, delete), so instead of writing every view twice the
views are written once and look up *which* kind they're serving from the
URL (`/exam-prep/<kind>/...`) through this registry. Adding a third kind
later (e.g. "Practice quizzes") means: one new model, one new form, one new
ExamKind entry below — no new views, urls or list template.
"""
from dataclasses import dataclass

from django.http import Http404

from .forms import PastQuestionForm, SummaryForm
from .models import PastQuestion, Summary


@dataclass(frozen=True)
class ExamKind:
    slug: str  # URL segment, e.g. "past-questions"
    model: type
    form: type
    label: str  # singular, for buttons and chips: "Past question"
    label_plural: str  # "Past questions"
    blurb: str  # one line shown on the hub card
    icon: str  # name of an icon in templates/partials/icons.html
    extra_select_related: tuple = ()  # extra joins the list/detail pages need
    extra_search_fields: tuple = ()  # extra fields the search box should also look in


PAST_QUESTIONS = ExamKind(
    slug=PastQuestion.kind_slug,
    model=PastQuestion,
    form=PastQuestionForm,
    label="Past question",
    label_plural="Past questions",
    blurb="Papers from previous examinations, by course and session.",
    icon="file-text",
)

SUMMARIES = ExamKind(
    slug=Summary.kind_slug,
    model=Summary,
    form=SummaryForm,
    label="Summary",
    label_plural="Summaries",
    blurb="Short, revision-ready summaries of handouts.",
    icon="layers",
    extra_select_related=("handout",),
    extra_search_fields=("handout__title",),
)

KINDS = {kind.slug: kind for kind in (PAST_QUESTIONS, SUMMARIES)}


def get_kind_or_404(slug):
    """Resolve a URL segment to its ExamKind, or 404 for anything we don't serve."""
    try:
        return KINDS[slug]
    except KeyError:
        raise Http404("Unknown exam-preparation section.") from None
