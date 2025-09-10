from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth.views import LoginView
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from .forms import ParticipantForm, ScreeningForm, SignupForm, DailyLogForm
from .models import Participant, ScreeningSession, Site, DailyLog
from axes.models import AccessAttempt
import logging


User = get_user_model()

# ---------------------- Helper Functions ----------------------

def get_user_participants(user):
    """Return participants visible to the user."""
    return Participant.objects.all() if user.is_superuser else Participant.objects.filter(site=user.site)


def pending_participants(participants):
    """Return participants with any missing items."""
    pending_list = []
    for p in participants:
        missing = []
        if not p.monitor_downloaded: missing.append("Monitor")
        if not p.ultrasound_downloaded: missing.append("Ultrasound")
        if not p.case_report_form_uploaded: missing.append("CRF")
        if not p.video_laryngoscope_uploaded: missing.append("Video Laryngoscope")
        if not p.rop_final_report_uploaded: missing.append("ROP Final Report")
        if not p.head_ultrasound_images_uploaded: missing.append("Head US Images")
        if not p.head_ultrasound_report_uploaded: missing.append("Head US Report")
        if not p.cost_effectiveness_data_uploaded: missing.append("Cost-Effect")
        if not p.blood_culture_done: missing.append("Blood Culture")
        if not p.admission_notes_day1_uploaded: missing.append("Notes Day 1")
        if missing:
            pending_list.append({'participant': p, 'missing': missing})
    return pending_list

def completed_participants(participants):
    """Return participants with everything completed."""
    completed = []
    for p in participants:
        if all([
            p.monitor_downloaded, p.ultrasound_downloaded, p.case_report_form_uploaded,
            p.video_laryngoscope_uploaded, p.rop_final_report_uploaded,
            p.head_ultrasound_images_uploaded, p.head_ultrasound_report_uploaded,
            p.cost_effectiveness_data_uploaded, p.blood_culture_done,
            p.admission_notes_day1_uploaded
        ]):
            completed.append(p)
    return completed

# ---------------------- Authentication Views ----------------------
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # Ensure site is selected for RA, RO, AD roles
            if user.role in ['RA', 'RO', 'AD'] and not user.site:
                messages.error(request, "Please select a site for your role.")
                return render(request, 'tracking/signup.html', {'form': form})

            user.is_active = False
            user.save()

            # Notify all active admins and superusers
            admins = User.objects.filter(is_active=True).filter(Q(role='AD') | Q(is_superuser=True))
            for admin in admins:
                if not admin.email:
                    continue
                approve_url = request.build_absolute_uri(reverse('tracking:approve_user', args=[user.pk]))
                reject_url = request.build_absolute_uri(reverse('tracking:reject_user', args=[user.pk]))
                send_mail(
                    subject=f"New Signup Pending Approval: {user.username} ({user.role})",
                    message=(
                        f"A new user has signed up.\n\n"
                        f"Username: {user.username}\nRole: {user.role}\nSite: {user.site}\n\n"
                        f"Approve: {approve_url}\nReject: {reject_url}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin.email],
                    fail_silently=False,
                )
            messages.success(request, "Account created successfully. An admin will review and activate your account shortly.")
            return redirect('tracking:login')
        messages.error(request, "Please correct the errors below.")
    else:
        form = SignupForm()
    return render(request, 'tracking/signup.html', {'form': form})


@login_required
def approve_user(request, user_id):
    if request.user.role != 'AD' and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {'message': "Only admins can approve users."})

    user = get_object_or_404(User, pk=user_id)
    user.is_active = True
    user.save()

    login_url = request.build_absolute_uri(reverse('tracking:login'))
    subject = "Your account has been approved ✅"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [user.email]

    text_content = f"Hello {user.username},\n\nYour account has been approved. You can now log in here: {login_url}"
    html_content = f"""
    <html><body>
    <p>Hello <strong>{user.username}</strong>,</p>
    <p>Your account has been <strong>approved</strong> and you can now access the system.</p>
    <p><a href="{login_url}" style="background-color:#007bff;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Click here to login</a></p>
    <p>Thank you,<br/>Preterm Africa Study Team</p>
    </body></html>
    """

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)

    messages.success(request, f"User {user.username} has been approved and activated.")
    return redirect('tracking:choose_dashboard')


@login_required
def reject_user(request, user_id):
    if request.user.role != 'AD' and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {'message': "Only admins can reject users."})

    user = get_object_or_404(User, pk=user_id)
    subject = "Your account has been rejected ❌"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [user.email]

    text_content = f"Hello {user.username},\n\nYour signup request has been rejected. Please contact the admin if you believe this is a mistake."
    html_content = f"""
    <html><body>
    <p>Hello <strong>{user.username}</strong>,</p>
    <p>Your signup request has been <strong>rejected</strong>.</p>
    <p>If you believe this is a mistake, please contact the admin.</p>
    <p>Thank you,<br/>Preterm Africa Study Team</p>
    </body></html>
    """

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)

    user.delete()
    messages.success(request, f"User {user.username} has been rejected and removed.")
    return redirect('tracking:choose_dashboard')


# ---------------------- Login Views (case-insensitive) ----------------------
class CaseInsensitiveLoginForm(AuthenticationForm):
    def clean_username(self):
        username = self.cleaned_data.get('username')
        return username.lower() if username else username

    def get_invalid_login_error(self):
        return ValidationError(
            "Incorrect username or password. Please try again.",
            code="invalid_login",
        )
#------------------Handles the Logins--------------------
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CaseInsensitiveLoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self._redirect_by_role(request.user)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()

        try:
            user = User.objects.get(username__iexact=username)

            # 🚨 If inactive, stop here (don’t validate password)
            if not user.is_active:
                form = self.authentication_form(request, data=request.POST)
                form.errors.clear()
                form.add_error(None, "Your account is not yet approved. Please wait for admin approval.")
                return self.form_invalid(form)

        except User.DoesNotExist:
            # If user doesn’t exist, stop here too
            form = self.authentication_form(request, data=request.POST)
            form.errors.clear()
            form.add_error(None, "Please Create an Account before attempting to login.")
            return self.form_invalid(form)

        # Only validate password if user exists AND is active
        form = self.authentication_form(request, data=request.POST)
        if form.is_valid():
            return self.form_valid(form)

        return self.form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return self._redirect_by_role(user)

    def _redirect_by_role(self, user):
        role_redirects = {
            'RA': 'tracking:ra_dashboard',
            'RO': 'tracking:ro_dashboard',
            'AD': 'tracking:choose_dashboard',
        }
        return redirect(role_redirects.get(getattr(user, "role", None), '/'))

#--------Logouts-------------------
@login_required
def custom_logout_view(request):
    logout(request)
    return redirect('tracking:login')

def auto_logout_view(request):
    logout(request)
    messages.warning(request, "Session timed out due to inactivity.")
    return redirect('tracking:login')
# ---------------------- Dashboard Views ----------------------

@login_required
def choose_dashboard(request):
    # Allow access if user is AD (PI), RO, RA, or superuser
    if getattr(request.user, "role", None) not in ['AD', 'RO', 'RA'] and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {
            'message': "Only PIs, ROs, RAs, or superusers can access this page."
        })

    # Superusers see all participants & screenings
    if request.user.is_superuser:
        participants = Participant.objects.all()
        screenings = ScreeningSession.objects.all()
    else:
        participants = get_user_participants(request.user)
        screenings = ScreeningSession.objects.filter(site=request.user.site)

    pending = pending_participants(participants)
    completed = completed_participants(participants)

    # Total number screened (from ScreeningSession)
    number_screened = screenings.aggregate(total=Sum('number_screened'))['total'] or 0

    # Site breakdown
    site_summary = (
        screenings.values('site__name')
        .annotate(
            total_screened=Sum('number_screened'),
            total_eligible=Sum('number_eligible'),
        )
        .order_by('site__name')
    )

    return render(request, 'tracking/choose_dashboard.html', {
        'participants': participants,
        'pending': pending,
        'completed': completed,
        'number_screened': number_screened,
        'site_summary': site_summary,
    })

@login_required(login_url=reverse_lazy('tracking:login'))
def ra_dashboard(request):
    if getattr(request.user, "role", None) not in ('RA', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {
            'message': "Only RAs, PIs, or superusers can access the dashboard."
        })

    participants = Participant.objects.all() if request.user.is_superuser else Participant.objects.filter(site=request.user.site)

    pending_list = [
        p for p in participants if not all([
            p.monitor_downloaded, p.ultrasound_downloaded, p.case_report_form_uploaded,
            p.video_laryngoscope_uploaded, p.rop_final_report_uploaded,
            p.head_ultrasound_images_uploaded, p.head_ultrasound_report_uploaded,
            p.cost_effectiveness_data_uploaded, p.blood_culture_done,
            p.admission_notes_day1_uploaded
        ])
    ]

    sorted_participants = sorted(pending_list, key=lambda p: p.enrollment_date, reverse=True)
    return render(request, 'tracking/ra_dashboard.html', {'participants': sorted_participants})


@login_required(login_url=reverse_lazy('tracking:login'))
def ro_dashboard(request):
    if getattr(request.user, "role", None) not in ('RO', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {
            'message': "Only ROs, PIs, or superusers can access the dashboard."
        })

    participants = get_user_participants(request.user)
    pending = [p for p in participants if p not in completed_participants(participants)]
    sorted_participants = sorted(pending, key=lambda p: p.days_remaining)
    return render(request, 'tracking/ro_dashboard.html', {'participants': sorted_participants})


# ---------------------- Participant Management ----------------------

@login_required
def register_participant(request):
    """Register a participant (RA/AD or superuser)."""
    if getattr(request.user, "role", None) not in ('RA', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {
            'message': "Only RAs, PIs, or superusers can register participants."
        })

    # Read ?eligible=N query param
    eligible_qs = request.GET.get("eligible")
    try:
        eligible_count = int(eligible_qs) if eligible_qs is not None else None
    except ValueError:
        eligible_count = None

    if request.method == 'POST':
        form = ParticipantForm(request.POST, user=request.user)
        if form.is_valid():
            participant = form.save(commit=False)

            # Ensure site assignment
            if not participant.site:
                if request.user.is_superuser:
                    messages.error(request, "Site must be selected for superuser registration.")
                    return render(request, 'tracking/participant_form.html', {
                        'form': form,
                        'eligible': eligible_count
                    })
                participant.site = request.user.site

            participant.save()
            messages.success(request, f"Participant {participant.study_id} registered.")

            # Determine which button was pressed
            if "add_another" in request.POST:
                return redirect(f"{reverse('tracking:register_participant')}?eligible={eligible_count}")
            return redirect('tracking:ra_dashboard')

        messages.error(request, "Please correct the errors below.")
    else:
        form = ParticipantForm(user=request.user)

    return render(request, 'tracking/participant_form.html', {
        'form': form,
        'eligible': eligible_count
    })


@login_required
def participant_detail(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if not request.user.is_superuser and participant.site != request.user.site:
        return render(request, 'tracking/forbidden.html', {
            'message': "You can only view participants from your site."
        })
    can_edit = (getattr(request.user, "role", None) in ['AD', 'RO']) or request.user.is_superuser
    return render(request, 'tracking/participant_detail.html', {
        'participant': participant,
        'can_edit': can_edit
    })


@login_required
def update_participant(request, pk):
    """Handle POST from participant_detail form; save checkboxes + comments."""
    participant = get_object_or_404(Participant, pk=pk)

    # Only RO, AD, or superuser can update via this form
    if not (getattr(request.user, "role", None) in ("RO", "AD") or request.user.is_superuser):
        return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})

    if request.method == "POST":
        ro_fields = [
            ("monitor_downloaded", "monitor_downloaded_comment"),
            ("ultrasound_downloaded", "ultrasound_downloaded_comment"),
            ("case_report_form_uploaded", "case_report_form_uploaded_comment"),
            ("video_laryngoscope_uploaded", "video_laryngoscope_uploaded_comment"),
            ("rop_final_report_uploaded", "rop_final_report_uploaded_comment"),
            ("head_ultrasound_images_uploaded", "head_ultrasound_images_uploaded_comment"),
            ("head_ultrasound_report_uploaded", "head_ultrasound_report_uploaded_comment"),
            ("cost_effectiveness_data_uploaded", "cost_effectiveness_data_uploaded_comment"),
            ("blood_culture_done", "blood_culture_done_comment"),
            ("admission_notes_day1_uploaded", "admission_notes_day1_uploaded_comment"),
            ("admission_notes_24hr_uploaded", "admission_notes_24hr_uploaded_comment"),
            ("vital_sign_monitoring_done", "vital_sign_monitoring_done_comment"),
        ]

        for checkbox_field, comment_field in ro_fields:
            # Save comment (store None if empty so template doesn't show "None")
            comment_value = (request.POST.get(comment_field) or "").strip()
            setattr(participant, comment_field, comment_value if comment_value else None)

            # Checkbox is true if explicitly checked OR a comment exists
            checkbox_value = request.POST.get(checkbox_field)
            setattr(participant, checkbox_field, bool(checkbox_value) or bool(comment_value))

        participant.save()
        messages.success(request, "Participant record updated successfully.")

        # Role-aware redirect
        if getattr(request.user, "role", None) == "RO":
            return redirect("tracking:ro_dashboard")
        if getattr(request.user, "role", None) == "AD" or request.user.is_superuser:
            return redirect("tracking:choose_dashboard")
        return redirect("tracking:participant_detail", pk=participant.pk)

    return redirect("tracking:participant_detail", pk=participant.pk)
# ---------------------- Quick Mark Actions ----------------------

@login_required(login_url=reverse_lazy('tracking:login'))
def mark_monitor_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (
            participant.site != request.user.site or getattr(request.user, "role", None) not in ('RO', 'AD')
        ):
            return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})

        participant.monitor_downloaded = True
        participant.monitor_downloaded_at = timezone.now()
        participant.monitor_downloaded_by = request.user
        participant.save()
        messages.success(request, f"Monitor download confirmed for {participant.study_id}")
    return redirect('tracking:ro_dashboard')


@login_required(login_url=reverse_lazy('tracking:login'))
def mark_ultrasound_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (
            participant.site != request.user.site or getattr(request.user, "role", None) not in ('RO', 'AD')
        ):
            return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})

        participant.ultrasound_downloaded = True
        participant.ultrasound_downloaded_at = timezone.now()
        participant.ultrasound_downloaded_by = request.user
        participant.save()
        messages.success(request, f"Ultrasound download confirmed for {participant.study_id}")
    return redirect('tracking:ro_dashboard')


# ---------------------- PDF Download ----------------------

@login_required
def download_completed_pdf(request):
    if getattr(request.user, "role", None) != 'AD' and not request.user.is_superuser:
        messages.error(request, "Only PIs or superusers can download PDF.")
        return redirect('tracking:choose_dashboard')

    participants = get_user_participants(request.user)
    participants = participants.filter(monitor_downloaded=True, ultrasound_downloaded=True)
    fully_completed = [
        p for p in participants if all([
            p.head_ultrasound_images_uploaded,
            p.head_ultrasound_report_uploaded,
            p.video_laryngoscope_uploaded,
            p.rop_final_report_uploaded,
            p.cost_effectiveness_data_uploaded,
            p.blood_culture_done,
        ])
    ]

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="completed_downloads.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=landscape(letter),
        rightMargin=20, leftMargin=20, topMargin=40, bottomMargin=20
    )
    elements = []

    title_style = ParagraphStyle(name='Title', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=20)
    site_name = "All Sites" if request.user.is_superuser else request.user.site.name
    elements.append(Paragraph(f"Preterm Africa Patient Tracking Log ({site_name})", title_style))

    wrap_style = ParagraphStyle(name='WrapStyle', fontName='Helvetica', fontSize=8, leading=10, wordWrap='LTR')

    headers = ["Study ID", "Enrollment Date", "Head US Images", "Head US Report",
               "Video Laryngoscope", "ROP Final Report", "Cost-Effect", "Blood Culture"]
    data = [[Paragraph(h, wrap_style) for h in headers]]

    for p in fully_completed:
        row = [
            Paragraph(p.study_id, wrap_style),
            Paragraph(p.enrollment_date.strftime("%b %d, %Y"), wrap_style),
            Paragraph("✔" if p.head_ultrasound_images_uploaded else "", wrap_style),
            Paragraph("✔" if p.head_ultrasound_report_uploaded else "", wrap_style),
            Paragraph("✔" if p.video_laryngoscope_uploaded else "", wrap_style),
            Paragraph("✔" if p.rop_final_report_uploaded else "", wrap_style),
            Paragraph("✔" if p.cost_effectiveness_data_uploaded else "", wrap_style),
            Paragraph("✔" if p.blood_culture_done else "", wrap_style),
        ]
        data.append(row)

    col_widths = [max(len(str(d.text)) for d in col) * 6 + 10 for col in zip(*data)]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#FFA94D")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
    ])
    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    return response


# ---------------------- Blog Page ----------------------

def blog(request):
    posts = [
        {'title': 'Preterm Study Brochure', 'description': 'Download our study brochure with details about recruitment and protocol.', 'link': '/static/docs/preterm_brochure.pdf'},
        {'title': 'Participant Guidelines', 'description': 'Guidelines for participants and their families.', 'link': '/static/docs/participant_guidelines.pdf'},
        {'title': 'AKU Partner Links', 'description': 'Useful links to partner resources.', 'link': 'https://www.aku.edu'}
    ]
    return render(request, 'tracking/blog.html', {'posts': posts})


def csrf_failure(request, reason=""):
    return render(request, "csrf_failure.html", status=403)


# ---------------------- Screening View ----------------------

@login_required
def screening_view(request):
    if request.method == "POST":
        try:
            number_screened = int(request.POST.get("number_screened", 0))
            number_eligible = int(request.POST.get("eligible", 0))
        except (TypeError, ValueError):
            messages.error(request, "Please enter valid whole numbers.")
            return HttpResponseRedirect(reverse("tracking:screening"))

        # Screening date (default today if not provided)
        screening_date = request.POST.get("screening_date")
        if not screening_date:
            from datetime import date
            screening_date = date.today()
        else:
            try:
                from datetime import datetime
                screening_date = datetime.strptime(screening_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid date format.")
                return HttpResponseRedirect(reverse("tracking:screening"))

        # Determine site
        site = None
        if getattr(request.user, "role", None) in ["RA", "RO"] and request.user.site:
            site = request.user.site
        elif request.user.is_superuser or getattr(request.user, "role", None) == "AD":
            site_id = request.POST.get("site_id")
            if site_id:
                try:
                    site = Site.objects.get(id=site_id)
                except Site.DoesNotExist:
                    messages.error(request, "Invalid site selected.")
                    return HttpResponseRedirect(reverse("tracking:screening"))
            else:
                messages.error(request, "No site found. Please select a site.")
                return HttpResponseRedirect(reverse("tracking:screening"))

        ScreeningSession.objects.create(
            ra=request.user,
            site=site,
            number_screened=number_screened,
            number_eligible=number_eligible,
            date=screening_date,  # ✅ matches model field
        )

        messages.success(request, f"Screening saved successfully. {number_eligible} participant(s) eligible")

        if number_eligible > 0:
            url = f"{reverse('tracking:register_participant')}?eligible={number_eligible}"
            return HttpResponseRedirect(url)

        if getattr(request.user, "role", None) == "RA":
            return HttpResponseRedirect(reverse("tracking:ra_dashboard"))
        if getattr(request.user, "role", None) == "RO":
            return HttpResponseRedirect(reverse("tracking:ro_dashboard"))
        return HttpResponseRedirect(reverse("tracking:choose_dashboard"))

    context = {}
    if request.user.is_superuser or getattr(request.user, "role", None) == "AD":
        context["sites"] = Site.objects.all()

    return render(request, "tracking/screening_form.html", context)


# ---------------------- Daily Activity Logs ----------------------

@login_required
def daily_log_view(request):
    if request.method == 'POST':
        form = DailyLogForm(request.POST, request.FILES)  # include request.FILES for uploads
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            return redirect('tracking:daily_logs')
    else:
        form = DailyLogForm(initial={'date': timezone.localdate()})

    logs = DailyLog.objects.filter(user=request.user)

    # Optional date filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        logs = logs.filter(date__range=[start_date, end_date])

    context = {
        'form': form,
        'logs': logs,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'tracking/daily_logs.html', context)

# ---------------------- Axes Custom Lockout View ----------------------
logger = logging.getLogger("axes.lockout")
def custom_lockout_view(request, credentials=None, *args, **kwargs):
    """
    Persistent Axes lockout page.
    Registered users -> 30 min lockout.
    Unregistered users -> permanent lockout until admin unblocks.
    """
    username = None
    ip_address = request.META.get("REMOTE_ADDR")
    remaining_seconds = 0
    permanent_lock = False

    if credentials:
        username = credentials.get("username", "").strip()

    if username:
        user_exists = User.objects.filter(username__iexact=username).exists()

        # Use the FIRST failed attempt to avoid countdown reset
        attempt = (
            AccessAttempt.objects.filter(username=username, ip_address=ip_address)
            .order_by("attempt_time")  # oldest first
            .first()
        )

        if attempt:
            if user_exists:
                # Registered user -> limited lockout period
                lockout_period = getattr(settings, "AXES_COOLOFF_TIME", 0.5) * 60 * 60
                elapsed = (timezone.now() - attempt.attempt_time).total_seconds()
                remaining_seconds = max(int(lockout_period - elapsed), 0)
            else:
                # Unregistered user -> permanent lock until admin clears
                permanent_lock = True
                # 🔐 Log permanent lock for admin review
                logger.warning(
                    f"Permanent lockout: username='{username}', "
                    f"IP={ip_address}, "
                    f"User-Agent={request.META.get('HTTP_USER_AGENT', 'unknown')}"
                )

    context = {
        "cool_off_seconds": remaining_seconds,
        "permanent_lock": permanent_lock,
        "blocked_username": username,
        "ip_address": ip_address,
    }
    return render(request, "tracking/account_locked.html", context)

