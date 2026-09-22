import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.explain.explain import (
    PRIORITY_LABELS,
    build_doctor_summary,
    format_list,
    render_dashboard,
)

__all__ = [
    "PRIORITY_LABELS",
    "build_doctor_summary",
    "format_list",
    "render_dashboard",
]
