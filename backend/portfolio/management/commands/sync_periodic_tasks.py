import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    PeriodicTasks,
    SolarSchedule,
)


DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2] / "config" / "periodic_tasks.json"
)


class Command(BaseCommand):
    help = "Sync django-celery-beat schedules from the version-controlled manifest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            default=str(DEFAULT_MANIFEST),
            help="Path to the periodic task manifest JSON file.",
        )

    def handle(self, *args, **options):
        manifest_path = Path(options["manifest"]).expanduser().resolve()
        if not manifest_path.exists():
            raise CommandError(f"Manifest file not found: {manifest_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {manifest_path}: {exc}") from exc

        if not isinstance(manifest, list):
            raise CommandError("Manifest must contain a list of periodic task definitions.")

        created = 0
        updated = 0

        with transaction.atomic():
            for item in manifest:
                task_name = item.get("name")
                if not task_name:
                    raise CommandError("Each task definition must include a non-empty 'name'.")

                schedule_defaults = self._resolve_schedule(item)
                defaults = {
                    "task": item["task"],
                    "interval": None,
                    "crontab": None,
                    "solar": None,
                    "clocked": None,
                    "args": json.dumps(item.get("args", [])),
                    "kwargs": json.dumps(item.get("kwargs", {})),
                    "queue": item.get("queue"),
                    "exchange": item.get("exchange"),
                    "routing_key": item.get("routing_key"),
                    "headers": json.dumps(item.get("headers", {})),
                    "priority": item.get("priority"),
                    "expires": self._parse_optional_datetime(item.get("expires"), "expires"),
                    "expire_seconds": item.get("expire_seconds"),
                    "one_off": item.get("one_off", False),
                    "start_time": self._parse_optional_datetime(item.get("start_time"), "start_time"),
                    "enabled": item.get("enabled", True),
                    "description": item.get("description", ""),
                }
                defaults.update(schedule_defaults)

                periodic_task, was_created = PeriodicTask.objects.update_or_create(
                    name=task_name,
                    defaults=defaults,
                )
                created += int(was_created)
                updated += int(not was_created)

                self.stdout.write(
                    f"{'Created' if was_created else 'Updated'} periodic task: {periodic_task.name}"
                )

            PeriodicTasks.update_changed()

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(manifest)} periodic tasks from {manifest_path} "
                f"({created} created, {updated} updated)."
            )
        )

    def _resolve_schedule(self, item):
        schedules = {
            "crontab": item.get("crontab"),
            "interval": item.get("interval"),
            "solar": item.get("solar"),
            "clocked": item.get("clocked"),
        }
        enabled_schedules = [name for name, value in schedules.items() if value]

        if len(enabled_schedules) != 1:
            raise CommandError(
                f"Task '{item.get('name')}' must define exactly one schedule type; "
                f"got {enabled_schedules or 'none'}."
            )

        schedule_type = enabled_schedules[0]
        schedule_spec = schedules[schedule_type]

        if schedule_type == "crontab":
            schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=schedule_spec["minute"],
                hour=schedule_spec["hour"],
                day_of_week=schedule_spec["day_of_week"],
                day_of_month=schedule_spec["day_of_month"],
                month_of_year=schedule_spec["month_of_year"],
                timezone=schedule_spec["timezone"],
            )
        elif schedule_type == "interval":
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=schedule_spec["every"],
                period=schedule_spec["period"],
            )
        elif schedule_type == "solar":
            schedule, _ = SolarSchedule.objects.get_or_create(
                event=schedule_spec["event"],
                latitude=schedule_spec["latitude"],
                longitude=schedule_spec["longitude"],
            )
        else:
            clocked_time = self._parse_optional_datetime(
                schedule_spec["clocked_time"],
                "clocked.clocked_time",
            )
            if clocked_time is None:
                raise CommandError(
                    f"Task '{item.get('name')}' has an invalid clocked_time value."
                )
            schedule, _ = ClockedSchedule.objects.get_or_create(clocked_time=clocked_time)

        return {schedule_type: schedule}

    def _parse_optional_datetime(self, value, field_name):
        if value in (None, ""):
            return None

        parsed = parse_datetime(value)
        if parsed is None:
            raise CommandError(f"Invalid datetime for '{field_name}': {value}")
        return parsed
