from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import Participant, Site, ScreeningSession,DailyLog

User = get_user_model()


# ---------- Screening Form (Step 1) ----------
class ScreeningForm(forms.ModelForm):
    number_screened = forms.IntegerField(
        required=True,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter number screened'})
    )
    number_eligible = forms.IntegerField(
        required=True,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter number eligible'})
    )

    class Meta:
        model = ScreeningSession
        fields = ['number_screened', 'number_eligible']

# ---------- Participant Form (Step 2) ----------
class ParticipantForm(forms.ModelForm):
    study_id = forms.CharField(
        max_length=3,
        validators=[RegexValidator(r'^\d{3}$', 'Enter exactly 3 digits')],
        widget=forms.TextInput(attrs={'placeholder': 'Enter 3-digit number', 'class': 'form-control'})
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    enrollment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Participant
        fields = ['study_id', 'date_of_birth', 'enrollment_date', 'site']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # RA users: auto-assign site and hide site field
        if self.user and getattr(self.user, 'role', None) == 'RA':
            self.fields.pop('site', None)
        elif self.user and self.user.role in ['AD', 'RO']:
            self.fields['site'].required = True

    def clean_study_id(self):
        number_part = self.cleaned_data.get('study_id')
        site = self.cleaned_data.get('site') or getattr(self.user, 'site', None)
        if not site:
            raise ValidationError("Site must be specified either by selection or your user profile.")

        full_study_id = f"{site}_{number_part}"
        qs = Participant.objects.filter(study_id=full_study_id)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("This Study ID is already registered. Please enter a unique Study ID.")
        return full_study_id

    def save(self, commit=True):
        participant = super().save(commit=False)
        if self.user and getattr(self.user, 'role', None) == 'RA':
            participant.site = self.user.site
        if commit:
            participant.save()
        return participant


# ---------- Participant Update Form (RO/Admin) ----------
class ParticipantUpdateForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            'monitor_downloaded', 'ultrasound_downloaded', 'case_report_form_uploaded',
            'video_laryngoscope_uploaded', 'rop_final_report_uploaded', 'head_ultrasound_images_uploaded',
            'head_ultrasound_report_uploaded', 'cost_effectiveness_data_uploaded', 'blood_culture_done',
            'admission_notes_day1_uploaded', 'admission_notes_24hr_uploaded'
        ]
        widgets = {field: forms.CheckboxInput(attrs={'class': 'form-check-input'}) for field in fields}


# ---------- Signup Form ----------
class SignupForm(UserCreationForm):
    ROLE_CHOICES = (
        ('RA', 'Research Assistant'),
        ('RO', 'Research Officer'),
        ('AD', 'PI'),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    site = forms.ModelChoiceField(queryset=Site.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}), required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'site', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already used. Please use a different email.")
        return email

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role not in dict(self.ROLE_CHOICES):
            raise forms.ValidationError("Invalid role selected.")
        return role

    def clean_site(self):
        site = self.cleaned_data.get('site')
        if not site:
            raise forms.ValidationError("Please select a site.")
        return site

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        site = cleaned_data.get('site')
        if role in ['RA', 'RO', 'AD'] and not site:
            self.add_error('site', 'This field is required for your role.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == 'AD' and not user.site:
            raise ValidationError("Admin users must have a site assigned.")
        if commit:
            user.save()
        return user

class DailyLogForm(forms.ModelForm):
    class Meta:
        model = DailyLog
        fields = ['date', 'title', 'tag', 'content']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg'}),
            'title': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Short title'}),
            'tag': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'content': forms.Textarea(attrs={'class': 'form-control form-control-lg', 'rows': 4, 'placeholder': 'Write your observation here...'}),
        }