from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from reconciliation.models import (
    Organization,
    InvestorEntity,
    CapitalCall,
    CapitalCallLineItem,
)
class Command(BaseCommand):

    def handle(self, *args, **options):
        rows = [
            ("northwind", "#1", date(2026, 3, 25), date(2026, 4, 10), "Haller Capital LLC", "CC-1001", "27500.00"),
            ("northwind", "#1", date(2026, 3, 25), date(2026, 4, 10), "Rahul Shah Trust", "CC-1002", "25000.00"),
            ("northwind", "#1", date(2026, 3, 25), date(2026, 4, 10), "Patel Family Trust", "CC-1003", "12500.00"),
            ("northwind", "#1", date(2026, 3, 25), date(2026, 4, 10), "Meridian Partners LP", "CC-1004", "15000.00"),
            ("northwind", "#1", date(2026, 3, 25), date(2026, 4, 10), "Oakridge Holdings LLC", "CC-1005", "15000.00"),
            ("northwind", "#2", date(2026, 4, 1), date(2026, 4, 20), "Oakridge Holdings LLC", "CC-1006", "15000.00"),
            ("bluebird", "#1", date(2026, 4, 1), date(2026, 4, 15), "Cedar Grove Fund LP", "CC-2001", "40000.00"),
        ]

        org_names = {
            "northwind": "Northwind Ventures",
            "bluebird": "Bluebird Capital",
        }

        for org_slug, call_id, c_date, d_date, inv_name, ref, amount in rows:
            org, _ = Organization.objects.get_or_create(
                slug=org_slug,
                defaults={"name": org_names[org_slug]},
            )

            call, _ = CapitalCall.objects.get_or_create(
                organization=org,
                identifier=call_id,
                defaults={"call_date": c_date, "due_date": d_date},
            )

            investor, _ = InvestorEntity.objects.get_or_create(
                organization=org,
                name=inv_name,
            )

            CapitalCallLineItem.objects.update_or_create(
                organization=org,
                expected_reference=ref,
                defaults={
                    "capital_call": call,
                    "investor_entity": investor,
                    "amount_called": Decimal(amount),
                    "amount_funded": Decimal("0.00"),
                    "status": "open",
                },
            )

        self.stdout.write("Demo data seeded.")