from django.core.management.base import BaseCommand

from drill.models import Fact
from drill.strategies import generate_facts


class Command(BaseCommand):
    help = ('Seed (or re-tag) the fact table, and delete facts that have left '
            'the domain (with their progress and attempts). Idempotent; safe '
            'to rerun.')

    def handle(self, *args, **options):
        created = updated = 0
        keep = set()
        for op, a, b, answer, strategy, stage, intro_order in generate_facts():
            fact, was_created = Fact.objects.update_or_create(
                operation=op, a=a, b=b,
                defaults={'answer': answer, 'strategy': strategy,
                          'stage': stage, 'intro_order': intro_order})
            keep.add(fact.pk)
            created += was_created
            updated += not was_created
        # a narrowed domain (say, exponent bases capped at 10) must not leave
        # the old facts behind: the scheduler would keep serving them
        gone = Fact.objects.exclude(pk__in=keep)
        removed = gone.count()
        gone.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Facts seeded: {created} created, {updated} updated, '
            f'{removed} removed, {Fact.objects.count()} total.'))
