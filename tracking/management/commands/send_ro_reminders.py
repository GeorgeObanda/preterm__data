from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from tracking.models import Participant, CustomUser


class Command(BaseCommand):
    help = "Send reminders for data downloads to ROs, RAs, Admins and escalate to PI if overdue"

    def handle(self, *args, **kwargs):
        reminders = {}   # {user: [(study_id, days_remaining, missing)]}
        escalations = [] # [(study_id, overdue_days, missing)]

        # Collect reminders and escalations
        participants = Participant.objects.all()
        for p in participants:
            days = p.days_remaining()
            missing = []
            if not p.monitor_downloaded:
                missing.append("Monitor")
            if not p.ultrasound_done:
                missing.append("Ultrasound")
            missing_str = ", ".join(missing) if missing else "None"

            if days in [2, 1, 0]:
                # Send to RA, RO, Admin of this site
                users = CustomUser.objects.filter(
                    role__in=["RA", "RO", "Admin"], site=p.site, is_active=True
                )
                for u in users:
                    reminders.setdefault(u, []).append((p.study_id, days, missing_str))

            elif days < 0:
                escalations.append((p.study_id, abs(days), missing_str))

        # --- Send reminders to RA, RO, Admin ---
        for user, items in reminders.items():
            subject = "Preterm Study Data Download Reminder"
            text_message = "You have participants nearing data download deadlines:\n"
            html_rows = ""

            for study_id, days, missing in items:
                if days == 2:
                    status = "Due in 2 days"
                elif days == 1:
                    status = "Due tomorrow"
                elif days == 0:
                    status = "DUE TODAY (URGENT)"
                text_message += f"- {study_id}: {status}, Missing: {missing}\n"
                html_rows += f"<tr><td>{study_id}</td><td>{status}</td><td>{missing}</td></tr>"

            html_message = f"""
            <p>Dear {user.username},</p>
            <p>The following participants at <b>{user.site}</b> require your attention:</p>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                <tr style="background-color:#f2f2f2;">
                    <th>Study ID</th>
                    <th>Status</th>
                    <th>Missing</th>
                </tr>
                {html_rows}
            </table>
            <p>Please log in to the system to take action:<br>
            <a href="{settings.SITE_URL}/login">{settings.SITE_URL}/login</a></p>
            """

            send_mail(
                subject,
                text_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
                html_message=html_message,
            )

        # --- Escalation to PI (CC Admin) if overdue ---
        if escalations:
            pis = CustomUser.objects.filter(role="PI", is_active=True)
            admins = CustomUser.objects.filter(role="Admin", is_active=True)

            if pis.exists():
                subject = "ESCALATION: Overdue Data Downloads in Preterm Study"
                text_message = "The following participants are overdue:\n"
                html_rows = ""

                for study_id, overdue_days, missing in escalations:
                    text_message += f"- {study_id}: overdue by {overdue_days} day(s), Missing: {missing}\n"
                    html_rows += f"<tr><td>{study_id}</td><td>{overdue_days}</td><td>{missing}</td></tr>"

                html_message = f"""
                <p>Dear PI,</p>
                <p>The following participants are <b>overdue</b> for data downloads:</p>
                <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                    <tr style="background-color:#f2f2f2;">
                        <th>Study ID</th>
                        <th>Days Overdue</th>
                        <th>Missing</th>
                    </tr>
                    {html_rows}
                </table>
                <p>Immediate action is required.</p>
                """

                recipient_list = list(pis.values_list("email", flat=True))
                cc_list = list(admins.values_list("email", flat=True))

                send_mail(
                    subject,
                    text_message,
                    settings.DEFAULT_FROM_EMAIL,
                    recipient_list + cc_list,  # PI + Admin together
                    fail_silently=False,
                    html_message=html_message,
                )

        self.stdout.write(self.style.SUCCESS("Reminders and escalations sent successfully"))
