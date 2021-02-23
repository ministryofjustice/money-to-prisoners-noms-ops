'use strict';

// design systems
import {initAll} from 'govuk-frontend';
initAll();

// mtp common components
import {initDefaults} from 'mtp_common';
import {initStaffDefaults} from 'mtp_common/staff-app';
import {AsyncLoad} from 'mtp_common/components/async-load';
import {DialogueBox} from 'mtp_common/components/dialogue-box';
import {PrintTrigger} from 'mtp_common/components/print-trigger';
import {TabbedPanel} from 'mtp_common/components/tabbed-panel';
initDefaults();
initStaffDefaults();
AsyncLoad.init();
DialogueBox.init();
PrintTrigger.init();
TabbedPanel.init();
