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
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from django.db.models import Q
from django.db.models import Sum
from datetime import datetime

from .models import Participant, ScreeningSession
from .forms import ParticipantForm, SignupForm

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
        if missing: pending_list.append({'participant': p, 'missing': missing})
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
            return redirect('tracking:ra_login')
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

    login_url = request.build_absolute_uri(reverse('tracking:ra_login'))
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
    """Override AuthenticationForm to allow case-insensitive usernames."""
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.lower()
        return username


class RAloginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CaseInsensitiveLoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self._redirect_by_role(request.user)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return self._redirect_by_role(user)

    def _redirect_by_role(self, user):
        if user.role == 'RA':
            return redirect('tracking:ra_dashboard')
        if user.role == 'RO':
            return redirect('tracking:ro_dashboard')
        if user.role == 'AD':
            return redirect('tracking:choose_dashboard')
        if user.is_superuser:
            return redirect('tracking:ra_dashboard')
        return redirect('/')


class ROloginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CaseInsensitiveLoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self._redirect_by_role(request.user)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return self._redirect_by_role(user)

    def _redirect_by_role(self, user):
        if user.role == 'RO':
            return redirect('tracking:ro_dashboard')
        if user.role == 'RA':
            return redirect('tracking:ra_dashboard')
        if user.role == 'AD':
            return redirect('tracking:choose_dashboard')
        if user.is_superuser:
            return redirect('tracking:ra_dashboard')
        return redirect('/')


@login_required
def custom_logout_view(request):
    logout(request)
    return redirect('tracking:ra_login')


def auto_logout_view(request):
    logout(request)
    messages.warning(request, "Session timed out due to inactivity.")
    return redirect('tracking:ra_login')


# ---------------------- Dashboard Views ----------------------

@login_required
def choose_dashboard(request):
    # Allow access if user is AD (PI) or superuser
    if request.user.role not in ['AD', 'RO'] and not request.user.is_superuser:
        return render(
            request,
            'tracking/forbidden.html',
            {'message': "Only PIs or superusers can access this page."}
        )

    # Superusers see all participants, AD sees only their assigned participants
    if request.user.is_superuser:
        participants = Participant.objects.all()
    else:
        participants = get_user_participants(request.user)

    pending = pending_participants(participants)
    completed = completed_participants(participants)

    # Total number screened (sum of number_screened column)
    number_screened = participants.aggregate(total_screened=Sum('number_screened'))['total_screened'] or 0

    return render(
        request,
        'tracking/choose_dashboard.html',
        {
            'participants': participants,
            'pending': pending,
            'completed': completed,
            'number_screened': number_screened
        }
    )
@login_required(login_url=reverse_lazy('tracking:ra_login'))
def ra_dashboard(request):
    if request.user.role not in ('RA', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {'message': "Only RAs, PIs, or superusers can access the dashboard."})

    participants = Participant.objects.all() if request.user.is_superuser else Participant.objects.filter(site=request.user.site)

    pending_participants = [p for p in participants if not all([
        p.monitor_downloaded, p.ultrasound_downloaded, p.case_report_form_uploaded,
        p.video_laryngoscope_uploaded, p.rop_final_report_uploaded,
        p.head_ultrasound_images_uploaded, p.head_ultrasound_report_uploaded,
        p.cost_effectiveness_data_uploaded, p.blood_culture_done,
        p.admission_notes_day1_uploaded
    ])]

    sorted_participants = sorted(pending_participants, key=lambda p: p.enrollment_date, reverse=True)
    return render(request, 'tracking/ra_dashboard.html', {'participants': sorted_participants})



@login_required(login_url=reverse_lazy('tracking:ro_login'))
def ro_dashboard(request):
    if request.user.role not in ('RO', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {'message': "Only ROs, PIs, or superusers can access the dashboard."})

    participants = get_user_participants(request.user)
    pending = [p for p in participants if p not in completed_participants(participants)]
    sorted_participants = sorted(pending, key=lambda p: p.days_remaining())
    return render(request, 'tracking/ro_dashboard.html', {'participants': sorted_participants})


# ---------------------- Participant Management ----------------------
@login_required
def register_participant(request):
    if request.method == "POST":
        form = ParticipantForm(request.POST, user=request.user)
        if form.is_valid():
            participant = form.save()
            messages.success(
                request,
                f"Participant {participant.study_id} saved. "
                f"Screened: {participant.number_screened}, Eligible: {participant.number_eligible}."
            )
            return redirect('tracking:register_participant')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ParticipantForm(user=request.user)

    return render(request, 'tracking/register_participant.html', {"form": form})
@login_required
def participant_detail(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if not request.user.is_superuser and participant.site != request.user.site:
        return render(request, 'tracking/forbidden.html', {'message': "You can only view participants from your site."})
    can_edit = request.user.role in ['AD', 'RO'] or request.user.is_superuser
    return render(request, 'tracking/participant_detail.html', {'participant': participant, 'can_edit': can_edit})


@login_required
def update_participant(request, pk):
    participant = get_object_or_404(Participant, pk=pk)

    # Permission check: RA, RO, AD, or superuser can update
    if request.user.role not in ('RA', 'RO', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html', {
            'message': "You do not have permission to update this participant."
        })

    # Optional: Ensure RA/RO/AD can only update participants from their site
    if request.user.role in ('RA', 'RO', 'AD') and not request.user.is_superuser:
        if participant.site != request.user.site:
            return render(request, 'tracking/forbidden.html', {
                'message': "Access Denied. Participant does not belong to your site."
            })

    if request.method == "POST":
        # Get form data
        study_id = request.POST.get("study_id")
        dob = request.POST.get("date_of_birth")
        enrollment = request.POST.get("enrollment_date")

        # Update fields if provided
        if study_id:
            participant.study_id = study_id
        if dob:
            participant.date_of_birth = dob
        if enrollment:
            participant.enrollment_date = enrollment

        participant.save()
        messages.success(request, f"Participant {participant.study_id} updated successfully.")

        # Redirect based on role
        if request.user.role == "RO":
            return redirect('tracking:ro_dashboard')
        elif request.user.role == "AD" or request.user.is_superuser:
            return redirect('tracking:choose_dashboard')
        else:
            return redirect('tracking:ra_dashboard')

    # If GET, redirect to participant detail
    return redirect('tracking:participant_detail', pk=participant.pk)




# ---------------------- Quick Mark Actions ----------------------

@login_required(login_url=reverse_lazy('tracking:ro_login'))
def mark_monitor_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (participant.site != request.user.site or request.user.role not in ('RO', 'AD')):
            return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})
        participant.monitor_downloaded = True
        participant.monitor_downloaded_at = timezone.now()
        participant.monitor_downloaded_by = request.user
        participant.save()
        messages.success(request, f"Monitor download confirmed for {participant.study_id}")
    return redirect('tracking:ro_dashboard')


@login_required(login_url=reverse_lazy('tracking:ro_login'))
def mark_ultrasound_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (participant.site != request.user.site or request.user.role not in ('RO', 'AD')):
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
    if request.user.role != 'AD' and not request.user.is_superuser:
        messages.error(request, "Only PIs or superusers can download PDF.")
        return redirect('tracking:choose_dashboard')

    participants = get_user_participants(request.user)
    participants = participants.filter(monitor_downloaded=True, ultrasound_downloaded=True)
    fully_completed = [p for p in participants if all([
        p.head_ultrasound_images_uploaded,
        p.head_ultrasound_report_uploaded,
        p.video_laryngoscope_uploaded,
        p.rop_final_report_uploaded,
        p.cost_effectiveness_data_uploaded,
        p.blood_culture_done,
    ])]

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="completed_downloads.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(letter),
                            rightMargin=20, leftMargin=20, topMargin=40, bottomMargin=20)
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FFA94D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ])
    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    return response

# ---------- Participant Management ----------

@login_required(login_url=reverse_lazy('tracking:ra_login'))
def register_participant(request):
    if request.user.role not in ('RA', 'AD') and not request.user.is_superuser:
        return render(request, 'tracking/forbidden.html',
                      {'message': "Only RAs, PIs, or superusers can register participants."})

    if request.method == 'POST':
        form = ParticipantForm(request.POST, user=request.user)
        if form.is_valid():
            participant = form.save(commit=False)

            # Assign site automatically if not superuser
            if not participant.site:
                if request.user.is_superuser:
                    messages.error(request, "Site must be selected for superuser registration.")
                    return render(request, 'tracking/participant_form.html', {'form': form})
                participant.site = request.user.site

            participant.save()
            messages.success(request, f"Participant {participant.study_id} registered.")
            return redirect('tracking:ra_dashboard')
    else:
        form = ParticipantForm(user=request.user)

    return render(request, 'tracking/participant_form.html', {'form': form})


@login_required
def participant_detail(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if not request.user.is_superuser and participant.site != request.user.site:
        return render(request, 'tracking/forbidden.html', {'message': "You can only view participants from your site."})
    can_edit = request.user.role in ['AD', 'RO'] or request.user.is_superuser
    return render(request, 'tracking/participant_detail.html', {'participant': participant, 'can_edit': can_edit})

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from tracking.models import Participant

@login_required
def update_participant(request, pk):
    participant = get_object_or_404(Participant, pk=pk)

    # RA: only participants from their site
    if request.user.role == 'RA' and participant.site != request.user.site:
        messages.error(request, "Access Denied. You can only modify participants from your site.")
        return redirect('tracking:ra_dashboard')

    # Block anyone else not allowed
    if request.user.role not in ('RA', 'RO', 'AD') and not request.user.is_superuser:
        messages.error(request, "You do not have permission to update this participant.")
        return redirect('tracking:ra_dashboard')

    if request.method == "POST":
        # --- Editable Fields ---

        # Study ID
        study_id = request.POST.get("study_id")
        if study_id is not None:
            participant.study_id = study_id.strip()

        # Date of Birth
        dob_str = request.POST.get("date_of_birth")
        if dob_str:
            try:
                participant.date_of_birth = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                messages.warning(request, "Invalid Date of Birth format. Use YYYY-MM-DD.")

        # Enrollment Date
        enrollment_str = request.POST.get("enrollment_date")
        if enrollment_str:
            try:
                participant.enrollment_date = datetime.strptime(enrollment_str, "%Y-%m-%d").date()
            except ValueError:
                messages.warning(request, "Invalid Enrollment Date format. Use YYYY-MM-DD.")

        # --- Checkboxes (for RO, AD, superuser) ---
        # RAs do not update checkboxes
        if request.user.role in ("RO", "AD") or request.user.is_superuser:
            checkbox_fields = [
                "monitor_downloaded",
                "ultrasound_downloaded",
                "case_report_form_uploaded",
                "video_laryngoscope_uploaded",
                "rop_final_report_uploaded",
                "head_ultrasound_images_uploaded",
                "head_ultrasound_report_uploaded",
                "cost_effectiveness_data_uploaded",
                "blood_culture_done",
                "admission_notes_day1_uploaded",
            ]
            for field in checkbox_fields:
                setattr(participant, field, field in request.POST)

        participant.save()
        messages.success(request, f"Participant {participant.study_id} updated successfully.")

        # Redirect based on role
        if request.user.role == "RA":
            return redirect('tracking:ra_dashboard')
        elif request.user.role == "RO":
            return redirect('tracking:ro_dashboard')
        elif request.user.role in ("AD",) or request.user.is_superuser:
            return redirect('tracking:choose_dashboard')

    # GET requests redirect to participant detail page
    return redirect('tracking:participant_detail', pk=participant.pk)

# ---------- Quick Mark Actions ----------

@login_required(login_url=reverse_lazy('tracking:ro_login'))
def mark_monitor_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (participant.site != request.user.site or request.user.role not in ('RO', 'AD')):
            return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})
        participant.monitor_downloaded = True
        participant.monitor_downloaded_at = timezone.now()
        participant.monitor_downloaded_by = request.user
        participant.save()
        messages.success(request, f"Monitor download confirmed for {participant.study_id}")
    return redirect('tracking:ro_dashboard')

@login_required(login_url=reverse_lazy('tracking:ro_login'))
def mark_ultrasound_downloaded(request, pk):
    if request.method == 'POST':
        participant = get_object_or_404(Participant, pk=pk)
        if not request.user.is_superuser and (participant.site != request.user.site or request.user.role not in ('RO', 'AD')):
            return render(request, 'tracking/forbidden.html', {'message': "Permission denied."})
        participant.ultrasound_downloaded = True
        participant.ultrasound_downloaded_at = timezone.now()
        participant.ultrasound_downloaded_by = request.user
        participant.save()
        messages.success(request, f"Ultrasound download confirmed for {participant.study_id}")
    return redirect('tracking:ro_dashboard')

# ---------- Blog Page ----------

def blog(request):
    posts = [
        {'title': 'Preterm Study Brochure', 'description': 'Download our study brochure with details about recruitment and protocol.', 'link': '/static/docs/preterm_brochure.pdf'},
        {'title': 'Participant Guidelines', 'description': 'Guidelines for participants and their families.', 'link': '/static/docs/participant_guidelines.pdf'},
        {'title': 'AKU Partner Links', 'description': 'Useful links to partner resources.', 'link': 'https://www.aku.edu'}
    ]
    return render(request, 'tracking/blog.html', {'posts': posts})

def csrf_failure(request, reason=""):
    return render(request, "csrf_failure.html", status=403)