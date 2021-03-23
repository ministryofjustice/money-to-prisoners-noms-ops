from django.utils.translation import gettext_lazy as _
from django import forms
from zendesk_tickets.forms import EmailTicketForm


class ContactUsForm(EmailTicketForm):
    ticket_content = forms.CharField(
        label=_('Please give details'),
        widget=forms.Textarea,
    )

    contact_email = forms.EmailField(
        label=_('Your email address'),
        required=True,
    )
