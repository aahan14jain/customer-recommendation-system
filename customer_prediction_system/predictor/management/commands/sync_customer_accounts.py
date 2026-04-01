"""
Create Django users and UserProfile rows for every existing Customer.

Idempotent: safe to run multiple times. Does not create or modify Customer rows.
Passwords are set only for newly created users unless --reset-password is passed.
"""

import os
import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from predictor.models import Customer, UserProfile


def _base_username(first_name: str, last_name: str) -> str:
    raw = f"{first_name or ''}{last_name or ''}".lower()
    raw = re.sub(r"[^a-z0-9]", "", raw)
    if not raw:
        raw = "customer"
    return raw[:120]


def _allocate_username(base: str) -> str:
    """Return a username starting with base, appending 2, 3, … if taken."""
    User = get_user_model()
    for i in range(1000):
        candidate = base if i == 0 else f"{base}{i + 1}"
        candidate = candidate[:150]
        if not User.objects.filter(username=candidate).exists():
            return candidate
    raise CommandError(f"Could not find a free username for base {base!r}")


class Command(BaseCommand):
    help = (
        "Create a Django User + UserProfile for each Customer. "
        "Uses DEFAULT_CUSTOMER_PASSWORD or --password (stored hashed via set_password)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Default password for newly created users (hashed; not stored as plain text). "
            "If omitted, uses DEFAULT_CUSTOMER_PASSWORD env var.",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Also reset password for existing users linked to customers (use with care).",
        )

    def handle(self, *args, **options):
        password_plain = options["password"] or os.environ.get(
            "DEFAULT_CUSTOMER_PASSWORD"
        )
        if not password_plain:
            raise CommandError(
                "Provide a default password: set DEFAULT_CUSTOMER_PASSWORD "
                'or pass --password "YourSecurePassword"'
            )

        User = get_user_model()
        reset_password = options["reset_password"]

        customers = Customer.objects.all().order_by("customer_id")
        total = customers.count()
        self.stdout.write(self.style.NOTICE(f"Processing {total} customer(s)…\n"))

        created_users = 0
        linked_profiles = 0
        skipped_existing = 0

        for customer in customers:
            with transaction.atomic():
                existing = UserProfile.objects.filter(customer=customer).select_related(
                    "user"
                ).first()

                if existing:
                    user = existing.user
                    if reset_password:
                        user.set_password(password_plain)
                        user.save(update_fields=["password"])
                    self.stdout.write(
                        f"[exists] username={user.username}\tcustomer_id={customer.customer_id}"
                    )
                    skipped_existing += 1
                    continue

                base = _base_username(customer.first_name, customer.last_name)
                username = _allocate_username(base)

                user = User(username=username, email="")
                user.set_password(password_plain)
                user.save()
                created_users += 1

                UserProfile.objects.create(user=user, customer=customer)
                linked_profiles += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[created] username={username}\tcustomer_id={customer.customer_id}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                f"Done. New users: {created_users}, "
                f"already linked (skipped): {skipped_existing}, "
                f"profiles created this run: {linked_profiles}."
            )
        )
