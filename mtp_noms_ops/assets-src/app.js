'use strict';

// design systems
import {initAll} from 'govuk-frontend';
initAll();

// mtp common components
import {initDefaults} from 'mtp_common';
import {initStaffDefaults} from 'mtp_common/staff-app';
import {AsyncLoad} from 'mtp_common/components/async-load';
import {AutocompleteSelect} from 'mtp_common/components/autocomplete-select';
import {Card} from 'mtp_common/components/card';
import {DialogueBox} from 'mtp_common/components/dialogue-box';
import {HiddenLongText} from 'mtp_common/components/hidden-long-text';
import {MailcheckWarning} from 'mtp_common/components/mailcheck-warning';
import {PrintTrigger} from 'mtp_common/components/print-trigger';
import {TabbedPanel} from 'mtp_common/components/tabbed-panel';
import {Upload} from 'mtp_common/components/upload';
initDefaults();
initStaffDefaults();
AsyncLoad.init();
AutocompleteSelect.init();
Card.init();
DialogueBox.init();
HiddenLongText.init();
MailcheckWarning.init(
  '.mtp-page-with-staff-email-input input[type=email]',
  ['justice.gov.uk'],
  ['gov.uk'],
  []
);
PrintTrigger.init();
TabbedPanel.init();
Upload.init();

// app components
import {CheckboxWithConditionalSubfields} from './components/checkbox-with-conditional-subfields';
import {ChoosePrisons} from './components/choose-prisons';
import {FormAnalytics} from './components/form-analytics';
import {Security} from './components/security';
CheckboxWithConditionalSubfields.init();
ChoosePrisons.init();
FormAnalytics.init();
Security.init();
