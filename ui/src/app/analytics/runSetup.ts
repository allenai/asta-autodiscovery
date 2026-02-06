import { mkTrackAttrs } from '@/analytics/track';

const PREFIX = 'run_setup' as const;

// Submit run button
export const mkSubmitRunBtnTrackAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${PREFIX}__submit_btn`, props);

// Expand advanced settings
export const mkExpandAdvancedSettingsTrackAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${PREFIX}__advanced_settings_btn`, props);
