import { mkTrackAttrs } from '@/analytics/track';

const SIDE_BAR_PREFIX = 'sidebar' as const;
const HEADER_PREFIX = 'header' as const;

// Logo
export const mkLogoTrackAttrs = (props: {} = {}) => mkTrackAttrs(`${SIDE_BAR_PREFIX}__logo`, props);

// Sidebar run item
export const mkRunListItemAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__run-list-item`, props);

// Delete run button
export const mkDeleteRunBtnAttrs = (props: { runId: string }) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__delete-run-btn`, props);

// Create new run button
export const mkCreateNewRunBtnAttrs = () => mkTrackAttrs(`${SIDE_BAR_PREFIX}__create-run-btn`);

// Responsible Use Link
export const mkResponsibleUseLinkTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__responsible_use_link`, props);

// Attribution Dialog Button
export const mkAttributionBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__attribution_btn`, props);

// Disclaimer Dialog Button
export const mkDisclaimerBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__disclaimer_btn`, props);

// Privacy Policy Link
export const mkPrivacyLinkTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__privacy_link`, props);

// ToS Link
export const mkTosLinkTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${SIDE_BAR_PREFIX}__tos_link`, props);

// Credits Button
export const mkCreditsBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${HEADER_PREFIX}__credits_btn`, props);

// Feedback Button
export const mkFeedbackBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${HEADER_PREFIX}__feedback_btn`, props);

// About Button
export const mkAboutBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${HEADER_PREFIX}__about_btn`, props);

// Login Button
export const mkLoginBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${HEADER_PREFIX}__login_btn`, props);

// Logout Button
export const mkLogoutBtnTrackAttrs = (props: {} = {}) =>
    mkTrackAttrs(`${HEADER_PREFIX}__logout_btn`, props);
