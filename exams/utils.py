"""
exams.utils
===========
Tiny helpers shared by the exams and materials views.
"""
from .models import PastQuestion, Summary


def course_resource_counts(course):
    """
    How much of each kind of study material one course has. Feeds the
    "Handouts | Past questions | Summaries" switcher
    (templates/partials/course_switcher.html), which is how a student hops
    between a course's handouts and its exam-preparation content.
    """
    return {
        "handouts": course.materials.count(),
        "past_questions": PastQuestion.objects.filter(course=course).count(),
        "summaries": Summary.objects.filter(course=course).count(),
    }
