from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from tracking.models import Participant, CustomUser, NotificationLog


class Command(BaseCommand):
    help = 'Send grouped reminders for data downloads/uploads'

    def handle(self, *args, **kwargs):
        participants = Participant.objects.all()
        reminders = {"due": [], "overdue": []}

        # Fetch active superusers
        superusers = list(CustomUser.objects.filter(is_superuser=True, is_active=True))

        # Collect missing items per participant
        for p in participants:
            days = p.days_remaining
            missing_items = []

            # ✅ Normal items (comment OR checkbox counts as complete)
            if not (p.monitor_downloaded or p.monitor_downloaded_comment):
                missing_items.append("Monitor Data")
            if not (p.ultrasound_downloaded or p.ultrasound_downloaded_comment):
                missing_items.append("Ultrasound Data")
            if not (p.case_report_form_uploaded or p.case_report_form_uploaded_comment):
                missing_items.append("Case Report Form")
            if not (p.video_laryngoscope_uploaded or p.video_laryngoscope_uploaded_comment):
                missing_items.append("Video Laryngoscope")

            # ✅ Special: ROP Exam (must be checked, comments don’t count)
            if not getattr(p, "rop_exam_done", False):
                missing_items.append("ROP Exam")

            # ✅ Special: ROP Final Report (must be checked, comments don’t count)
            if getattr(p, "rop_exam_done", False):  # only relevant if exam already done
                if not p.rop_final_report_uploaded:
                    missing_items.append("ROP Final Report")

            # ✅ Normal items again
            if not (p.head_ultrasound_images_uploaded or p.head_ultrasound_images_uploaded_comment):
                missing_items.append("Head US Images")
            if not (p.head_ultrasound_report_uploaded or p.head_ultrasound_report_uploaded_comment):
                missing_items.append("Head US Report")
            if not (p.cost_effectiveness_data_uploaded or p.cost_effectiveness_data_uploaded_comment):
                missing_items.append("Cost Effectiveness Data")
            if not (p.blood_culture_done or p.blood_culture_done_comment):
                missing_items.append("Blood Culture")
            if not (p.admission_notes_day1_uploaded or p.admission_notes_day1_uploaded_comment):
                missing_items.append("Admission Notes Day 1")

            if not missing_items:
                continue

            # Add explicit ROP due note
            rop_note = ""
            if "ROP Exam" in missing_items:
                if p.rop_due_date:
                    rop_note = f"<br><small style='color:#d9534f;'>ROP Exam due: {p.rop_due_date}</small>"
                else:
                    rop_note = "<br><small style='color:#d9534f;'>ROP Exam due date not available</small>"

            row = f"""
            <tr>
                <td style="padding:8px; border:1px solid #ddd;">{p.study_id}</td>
                <td style="padding:8px; border:1px solid #ddd;">{', '.join(missing_items)}{rop_note}</td>
                <td style="padding:8px; text-align:center; border:1px solid #ddd;">{days if days >= 0 else 'Overdue'}</td>
            </tr>
            """

            if days in [2, 1, 0]:
                reminders["due"].append((p.site, row, days, p, missing_items))
            elif days < 0:
                reminders["overdue"].append((p.site, row, days, p, missing_items))

        # Build HTML table
        def build_html_table(rows, title, highlight_color):
            return f"""
            <div style="border:1px solid #e1e1e1; border-radius:10px; padding:20px;
                        margin:20px 0; box-shadow:0 4px 8px rgba(0,0,0,0.08); font-family:Arial,sans-serif; color:#444;">
                <h2 style="color:{highlight_color}; font-size:20px; margin-bottom:15px;">{title}</h2>
                <table style="border-collapse:collapse; width:100%; font-size:14px;">
                    <thead>
                        <tr style="background-color:#f1f1f1; text-align:left;">
                            <th style="padding:10px; border:1px solid #ddd;">Study ID</th>
                            <th style="padding:10px; border:1px solid #ddd;">Missing Items</th>
                            <th style="padding:10px; text-align:center; border:1px solid #ddd;">Days Remaining</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
            """

        # Helper to send emails
        def send_email(subject, table_html, recipients_list, status_color="#f0ad4e"):
            for user in recipients_list:
                name = f"{user.first_name} {user.last_name}".strip() or user.username
                body_html = f"""
                <div style="font-family:Arial,sans-serif; color:#444; font-size:14px; line-height:1.6;">
                    <p>Dear {name},</p>
                    <p>The following uploads are <strong style="color:{status_color};">{'OVERDUE' if status_color=='#d9534f' else 'pending'}</strong>:</p>
                    {table_html}
                    <p style="text-align:center; margin:20px 0;">
                        <a href="https://preterm-data-tracker-9zcd.onrender.com" 
                           style="background-color:{status_color}; color:white; padding:12px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">
                            🔗 {'Follow Up Now' if status_color=='#d9534f' else 'Login to Update'}
                        </a>
                    </p>
                    <p style="font-size:12px; color:#888; text-align:center;">Automated alert from <b>Preterm Baby Tracker</b>.</p>
                </div>
                """
                msg = EmailMultiAlternatives(subject, body_html, settings.DEFAULT_FROM_EMAIL, [user.email])
                msg.attach_alternative(body_html, "text/html")
                msg.send()

        # ================= SEND DUE REMINDERS =================
        if reminders["due"]:
            for site in set(r[0] for r in reminders["due"]):
                site_rows = [r[1] for r in reminders["due"] if r[0] == site]
                site_days = [r[2] for r in reminders["due"] if r[0] == site]
                subject = f"Pending uploads due soon (Days-{min(site_days)})"
                table_html = build_html_table(site_rows, "Pending Uploads – Due Soon", "#f0ad4e")
                recipients = list(CustomUser.objects.filter(role__in=['RO','RA','AD'], site=site, is_active=True)) + superusers

                send_email(subject, table_html, recipients, status_color="#f0ad4e")

                # Log notifications & send PI critical alerts
                for user in recipients:
                    for r in reminders["due"]:
                        NotificationLog.objects.create(participant=r[3], notification_type='DAILY_PROMPT', recipient=user)
                        if user.is_superuser and user.role == "PI":
                            critical_items = [i for i in ['Ultrasound Data','Blood Culture','ROP Exam','ROP Final Report'] if i in r[4]]
                            if critical_items:
                                critical_html = build_html_table(
                                    [f"<tr><td>{r[3].study_id}</td><td>{', '.join(critical_items)}</td><td>{r[2] if r[2]>=0 else 'Overdue'}</td></tr>"],
                                    "Critical Pending Items – PI Attention Required",
                                    "#d9534f"
                                )
                                pi_subject = f"🚨 Critical Pending Items for {r[3].study_id}"
                                send_email(pi_subject, critical_html, [user], status_color="#d9534f")

        # ================= SEND OVERDUE REMINDERS =================
        if reminders["overdue"]:
            rows = [r[1] for r in reminders["overdue"]]
            subject = "🚨 Overdue uploads – Immediate Action Required"
            table_html = build_html_table(rows, "Overdue Uploads", "#d9534f")
            recipients = list(CustomUser.objects.filter(role__in=['RO','RA','AD'], is_active=True)) + superusers

            send_email(subject, table_html, recipients, status_color="#d9534f")

            # Log notifications & send PI critical alerts
            for user in recipients:
                for r in reminders["overdue"]:
                    NotificationLog.objects.create(participant=r[3], notification_type='OVERDUE_ALERT', recipient=user)
                    if user.is_superuser and user.role == "PI":
                        critical_items = [i for i in ['Ultrasound Data','Blood Culture','ROP Exam','ROP Final Report'] if i in r[4]]
                        if critical_items:
                            critical_html = build_html_table(
                                [f"<tr><td>{r[3].study_id}</td><td>{', '.join(critical_items)}</td><td>{r[2] if r[2]>=0 else 'Overdue'}</td></tr>"],
                                "Critical Pending Items – PI Attention Required",
                                "#d9534f"
                            )
                            pi_subject = f"🚨 Critical Pending Items for {r[3].study_id}"
                            send_email(pi_subject, critical_html, [user], status_color="#d9534f")

        self.stdout.write(self.style.SUCCESS("All reminders, superuser copies, and PI alerts sent successfully"))
