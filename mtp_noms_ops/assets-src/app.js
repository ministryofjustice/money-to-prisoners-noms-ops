'use strict';

// design systems
import {initAll} from 'govuk-frontend';
initAll();

// mtp common components
import {initDefaults} from 'mtp_common';
import {initStaffDefaults} from 'mtp_common/staff-app';
import {DialogueBox} from 'mtp_common/components/dialogue-box';
initDefaults();
initStaffDefaults();
DialogueBox.init();
