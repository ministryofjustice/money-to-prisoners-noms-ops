from mtp_common.security.checks import (
    CHECK_REJECTION_BOOL_CATEGORY_LABELS,
    CHECK_REJECTION_TEXT_CATEGORY_LABELS,
)

SECURITY_FORMS_DEFAULT_PAGE_SIZE = 20

# This is as custom-defined exception within the API service that we match against
CHECK_AUTO_ACCEPT_UNIQUE_CONSTRAINT_ERROR = \
    'An existing AutoAcceptRule is present for this DebitCardSenderDetails/PrisonerProfile pair'

CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS = dict(
    (code, label)
    for code, label in CHECK_REJECTION_BOOL_CATEGORY_LABELS.items()
    if code not in {'payment_source_known_email'}
)
CURRENT_CHECK_REJECTION_TEXT_CATEGORY_LABELS = dict(
    (code, label)
    for code, label in CHECK_REJECTION_TEXT_CATEGORY_LABELS.items()
    if code not in {'fiu_investigation_id'}
)

CURRENT_CHECK_REJECTION_CATEGORIES = set(CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS) \
                                     | set(CURRENT_CHECK_REJECTION_TEXT_CATEGORY_LABELS)
