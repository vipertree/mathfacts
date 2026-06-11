from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from drill.models import Student
from drill.themes import THEMES


class Command(BaseCommand):
    help = 'Create a student account (username + password, no email).'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('password')
        parser.add_argument('--theme', default='pirate', choices=sorted(THEMES))
        parser.add_argument('--goal', type=int, default=150,
                            help='daily goal in points (default 150 ≈ 15 min)')

    def handle(self, *args, **options):
        if User.objects.filter(username=options['username']).exists():
            raise CommandError(f"user '{options['username']}' already exists")
        user = User.objects.create_user(
            username=options['username'], password=options['password'])
        Student.objects.create(
            user=user, theme=options['theme'], daily_goal_points=options['goal'])
        if options['verbosity']:
            self.stdout.write(self.style.SUCCESS(
                f"Student '{user.username}' created (theme: {options['theme']}, "
                f"goal: {options['goal']} pts)."))
