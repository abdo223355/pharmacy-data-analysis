"""Pharmacist / branch / shift configuration.

Real names live in scripts/config_local.py (git-ignored). Copy config_local.example.py to
config_local.py and fill it in. Without it the scripts fall back to generic placeholder names.
"""
try:
    from config_local import PHARMACISTS  # noqa: F401
except ImportError:
    PHARMACISTS = [
        # (name in the sheet, Arabic display name, branch, shift)
        ("Dr. A", "د. أ", "Mut - Dakhla", "morning"),
        ("Dr. B", "د. ب", "Mut - Dakhla", "night"),
        ("Dr. C", "د. ج", "Kharga", "morning"),
        ("Dr. D", "د. د", "Kharga", "night"),
    ]

HOME_BRANCH = {name: branch for name, _, branch, _ in PHARMACISTS}      # pharmacist -> branch
SHIFT_DOCTOR = {(branch, shift): name for name, _, branch, shift in PHARMACISTS}  # (branch, shift) -> pharmacist
DOCTOR_AR = {name: name_ar for name, name_ar, _, _ in PHARMACISTS}      # pharmacist -> Arabic display name
