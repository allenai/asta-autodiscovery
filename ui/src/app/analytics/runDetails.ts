import { mkTrackAttrs } from '@/analytics/track';

const RUN_DETAILS = 'run_details' as const;

// Experiment Row
export const mkExperimentRowAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${RUN_DETAILS}__experiment-row`, props);

// Session Configuration Button
export const mkSessionConfigBtnAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__session_config_btn`, props);

// Close experiments details panel
export const mkCloseExperimentDetailsPanelAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__close_experiment_details_panel`, props);

// Sort column event name
export const sortColumnEventName = `${RUN_DETAILS}__sort_column` as const;

// Download button click
export const mkDownloadBtnAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__download_btn`, props);

// Download CSV menu item click
export const mkDownloadCsvMenuItemAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__download_csv`, props);

// Download JSON menu item click
export const mkDownloadJsonMenuItemAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__download_json`, props);

// Explore with Asta table link click (opens modal from experiments table)
export const mkExploreWithAstaTableLinkAttrs = (props: { runId: string; experimentId: string }) =>
    mkTrackAttrs(`${RUN_DETAILS}__explore_with_asta_table_link`, props);

// Continue exploring with Asta button click (opens modal from experiment detail panel)
export const mkContinueExploringWithAstaBtnAttrs = (props: {
    runId: string;
    experimentId: string;
}) => mkTrackAttrs(`${RUN_DETAILS}__continue_exploring_with_asta_btn`, props);

// Start Asta exploration event name (fired when user confirms and launches Asta)
export const startAstaExplorationEventName =
    `${RUN_DETAILS}__start_asta_exploration` as const;
