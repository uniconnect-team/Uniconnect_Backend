from django.core.management.base import BaseCommand
from apps.users.models import Profile


class Command(BaseCommand):
    help = 'Reset all user profiles to incomplete status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Reset only for specific user email',
        )

    def handle(self, *args, **options):
        email = options.get('email')
        
        if email:
            try:
                profile = Profile.objects.get(user__email__iexact=email)
                profile.profile_completed = False
                profile.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Reset profile for {email}')
                )
            except Profile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'No profile found for {email}')
                )
        else:
            count = Profile.objects.all().update(profile_completed=False)
            self.stdout.write(
                self.style.SUCCESS(f'Reset {count} profiles to incomplete')
            )



