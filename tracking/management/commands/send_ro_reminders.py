from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from tracking.models import Participant, CustomUser


class Command(BaseCommand):
    help = 'Send grouped reminders for data downloads/uploads'

    def handle(self, *args, **kwargs):
        participants = Participant.objects.all()

        # Prepare grouped missing items per participant
        reminders = {"due": [], "overdue": []}

        for p in participants:
            days = p.days_remaining()

            # Collect missing items
            missing_items = []
            checks = {
                "Monitor Downloaded": p.monitor_downloaded,
                "Ultrasound Downloaded": p.ultrasound_downloaded,
                "Case Report Form": p.case_report_form_uploaded,
                "Video Laryngoscope": p.video_laryngoscope_uploaded,
                "ROP Final Report": p.rop_final_report_uploaded,
                "Head US Images": p.head_ultrasound_images_uploaded,
                "Head US Report": p.head_ultrasound_report_uploaded,
                "Cost Effectiveness Data": p.cost_effectiveness_data_uploaded,
                "Blood Culture": p.blood_culture_done,
                "Admission Notes Day 1": p.admission_notes_day1_uploaded,
            }

            for label, status in checks.items():
                if not status:
                    missing_items.append(label)

            if not missing_items:
                continue

            # Build row: StudyID | all missing items | Days remaining
            row = f"""
            <tr>
                <td>{p.study_id}</td>
                <td>{', '.join(missing_items)}</td>
                <td style="text-align:center;">{days if days >= 0 else 'Overdue'}</td>
            </tr>
            """

            if days in [2, 1, 0]:
                reminders["due"].append((p.site, row, days))
            elif days < 0:
                reminders["overdue"].append((p.site, row, days))

        # Function to format HTML table inside styled card
        def build_html_table(rows, title, highlight_color):
            return f"""
            <div style="border:1px solid #ddd; border-radius:10px; padding:15px; 
                        margin:20px 0; box-shadow:1px 2px 6px rgba(0,0,0,0.08);
                        font-family:Arial, sans-serif; font-size:14px; color:#333;">
                <h3 style="color:{highlight_color}; margin-top:0;">{title}</h3>
                <table border="1" cellpadding="8" cellspacing="0" 
                       style="border-collapse: collapse; width:100%; font-size:13px;">
                    <tr style="background-color:#f9f9f9; text-align:left;">
                        <th style="padding:8px;">Study ID</th>
                        <th style="padding:8px;">Missing Items</th>
                        <th style="padding:8px; text-align:center;">Days Remaining</th>
                    </tr>
                    {''.join(rows)}
                </table>
            </div>
            """

        # Send Due reminders
        if reminders["due"]:
            for site in set(r[0] for r in reminders["due"]):
                rows = [r[1] for r in reminders["due"] if r[0] == site]
                days_list = [r[2] for r in reminders["due"] if r[0] == site]
                subject = f"⚠️ Pending uploads due soon (D-{min(days_list)})"
                table_html = build_html_table(rows, "Pending Uploads – Due Soon", "#f0ad4e")

                recipients = CustomUser.objects.filter(
                    role__in=['RO', 'RA', 'AD'], site=site, is_active=True
                )

                for user in recipients:
                    body_html = f"""
                    <div style="font-family:Arial, sans-serif; color:#333; font-size:14px;">
                        <p>Dear {user.username},</p>
                        <p>The following uploads are still pending and need your attention:</p>
                        {table_html}
                        <p style="margin:20px 0;">
                            <a href="https://preterm-data-tracker-9zcd.onrender.com"
                               style="background-color:#0275d8; color:white; padding:10px 16px; 
                                      border-radius:5px; text-decoration:none; font-weight:bold;">
                                Login to Update
                            </a>
                        </p>
                        <p>Best regards,<br>
                        <strong>Preterm Baby Tracker System</strong></p>
                    </div>
                    """

                    msg = EmailMultiAlternatives(
                        subject,
                        body_html,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                    )
                    msg.attach_alternative(body_html, "text/html")
                    msg.send()

        # Send Overdue reminders
        if reminders["overdue"]:
            rows = [r[1] for r in reminders["overdue"]]
            subject = "🚨 Overdue uploads – Immediate Action Required"
            table_html = build_html_table(rows, "Overdue Uploads", "#d9534f")

            recipients = CustomUser.objects.filter(role='AD', is_active=True)

            for user in recipients:
                body_html = f"""
                <div style="font-family:Arial, sans-serif; color:#333; font-size:14px;">
                    <p>Dear {user.username},</p>
                    <p>The following uploads are <b style="color:#d9534f;">overdue</b>:</p>
                    {table_html}
                    <p style="margin:20px 0;">
                        <a href="https://preterm-data-tracker-9zcd.onrender.com"
                           style="background-color:#d9534f; color:white; padding:10px 16px; 
                                  border-radius:5px; text-decoration:none; font-weight:bold;">
                            Follow Up Now
                        </a>
                    </p>
                    <p>Best regards,<br>
                    <strong>Preterm Baby Tracker System</strong></p>
                </div>
                """

                msg = EmailMultiAlternatives(
                    subject,
                    body_html,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
                msg.attach_alternative(body_html, "text/html")
                msg.send()

        self.stdout.write(self.style.SUCCESS("Grouped reminders sent successfully"))
