from django.utils.translation import gettext_lazy as _


CHECK_REJECTION_CATEGORY_TEXT_MAPPING = {
    'fiu_investigation_id': _('Associated FIU investigation'),
    'intelligence_report_id': _('Associated intelligence report (IR)'),
    'other_reason': _('Other reason'),
}
CHECK_REJECTION_CATEGORY_BOOLEAN_MAPPING = {
    'payment_source_paying_multiple_prisoners': _('Payment source is paying multiple prisoners'),
    'payment_source_multiple_cards': _('Payment source is using multiple cards'),
    'payment_source_linked_other_prisoners': _('Payment source is linked to other prisoner/s'),
    'payment_source_known_email': _('Payment source is using a known email'),
    'payment_source_unidentified': _('Payment source is unidentified'),
    'prisoner_multiple_payments_payment_sources': _('Prisoner has multiple payments or payment sources')
}

CHECK_DETAIL_RENDERED_MAPPING = dict(
    tuple(CHECK_REJECTION_CATEGORY_TEXT_MAPPING.items()) + tuple(CHECK_REJECTION_CATEGORY_BOOLEAN_MAPPING.items())
)

CHECK_DETAIL_FORM_MAPPING = {
    'decision_reason': _('Give further details (optional)'),
    'rejection_reasons': dict(
        tuple(CHECK_REJECTION_CATEGORY_TEXT_MAPPING.items()) + tuple(CHECK_REJECTION_CATEGORY_BOOLEAN_MAPPING.items())
    )
}
