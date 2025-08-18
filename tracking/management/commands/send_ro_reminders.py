from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from tracking.models import Participant, CustomUser

class Command(BaseCommand):
    help = 'Send RO reminders for data downloads based on days remaining'

    def handle(self, *args, **kwargs):
        participants = Participant.objects.all()
        for p in participants:
            days = p.days_remaining()
            if days in [0, 1]:
                ros = CustomUser.objects.filter(role='RO', site=p.site, is_active=True)
                for ro in ros:
                    if days == 1:
                        subject = f"Reminder: Data download for {p.study_id} tomorrow"
                        message = f"Participant {p.study_id} is due for data download tomorrow."
                    else:  # days == 0
                        subject = f"Urgent: Data download for {p.study_id} today"
                        message = f"Participant {p.study_id} requires data download today."
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [ro.email],
                        fail_silently=False
                    )
        self.stdout.write(self.style.SUCCESS('RO reminders sent successfully'))
