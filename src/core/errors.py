"""Eksepsi bersama — dipakai engine dan converter tanpa circular import."""


class TaskCancelled(Exception):
    """Dilempar converter saat user membatalkan task."""
