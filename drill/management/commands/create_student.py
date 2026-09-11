from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from drill.models import DEFAULT_OPERATIONS, OP_ORDER, Student, clean_operations
from drill.themes import THEMES


class Command(BaseCommand):
    help = 'Create a student account (username + password, no email).'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('password')
        parser.add_argument('--theme', default='pirate', choices=sorted(THEMES))
        parser.add_argument('--goal', type=int, default=150,
                            help='daily goal in points (default 150 ≈ 15 min)')
        parser.add_argument(
            '--operations', '--ops', dest='operations', nargs='+',
            choices=OP_ORDER, default=list(DEFAULT_OPERATIONS),
            metavar='OP',
            help='operations to practice: any of %s (default: %s)'
                 % (' '.join(OP_ORDER), ' '.join(DEFAULT_OPERATIONS)))

    def handle(self, *args, **options):
        if User.objects.filter(username=options['username']).exists():
            raise CommandError(f"user '{options['username']}' already exists")
        operations = clean_operations(options['operations'])
        if not operations:
            raise CommandError('--operations needs at least one of: %s'
                               % ' '.join(OP_ORDER))
        user = User.objects.create_user(
            username=options['username'], password=options['password'])
        Student.objects.create(
            user=user, theme=options['theme'], daily_goal_points=options['goal'],
            operations=operations)
        if options['verbosity']:
            self.stdout.write(self.style.SUCCESS(
                f"Student '{user.username}' created (theme: {options['theme']}, "
                f"goal: {options['goal']} pts, practices: "
                f"{' '.join(operations)})."))
