from django.core.management.base import BaseCommand

from drill.models import Fact
from drill.strategies import generate_facts


class Command(BaseCommand):
    help = 'Seed (or re-tag) the fact table. Idempotent; safe to rerun.'

    def handle(self, *args, **options):
        created = updated = 0
        for op, a, b, answer, strategy, stage, intro_order in generate_facts():
            _, was_created = Fact.objects.update_or_create(
                operation=op, a=a, b=b,
                defaults={'answer': answer, 'strategy': strategy,
                          'stage': stage, 'intro_order': intro_order})
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f'Facts seeded: {created} created, {updated} updated, '
            f'{Fact.objects.count()} total.'))
