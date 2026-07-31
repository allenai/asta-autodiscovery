'use client';

import { styled, Theme } from '@mui/material';
import { useState } from 'react';

import { DisclaimerDialog } from './DisclaimerDialog';
import { AttributionDialog } from './AttributionDialog';
import {
    mkAttributionBtnTrackAttrs,
    mkDisclaimerBtnTrackAttrs,
    mkFeedbackBtnTrackAttrs,
    mkPrivacyLinkTrackAttrs,
    mkResponsibleUseLinkTrackAttrs,
    mkTosLinkTrackAttrs,
} from '@/analytics/run';
import {
    TEST_ID_ATTRIBUTION_BUTTON,
    TEST_ID_DISCLAIMER_BUTTON,
    TEST_ID_FEEDBACK_BUTTON,
    TEST_ID_PRIVACY_POLICY_LINK,
    TEST_ID_RESPONSIBLE_USE_LINK,
    TEST_ID_TERMS_OF_USE_LINK,
} from '@/testIds';

const FEEDBACK_URL =
    'https://docs.google.com/forms/d/e/1FAIpQLScmKqOj9EuOrfNlO0ySm_5ITPH80anDgC3FDBuSEeesgztv1Q/viewform';

/**
 * The link/action list rendered inside the user menu popover.
 */
export const MenuLinks = ({ layout = 'menu' }: { layout?: 'menu' | 'settings' }) => {
    const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
    const [isAttributionOpen, setIsAttributionOpen] = useState(false);

    return (
        <>
            <LinksSection>
                <SettingsLink
                    href={FEEDBACK_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-test-id={TEST_ID_FEEDBACK_BUTTON}
                    {...mkFeedbackBtnTrackAttrs()}>
                    Leave Feedback
                </SettingsLink>
                {layout === 'settings' && (
                    <>
                        <SettingsButton
                            type="button"
                            aria-haspopup="dialog"
                            onClick={() => setIsDisclaimerOpen(true)}
                            data-test-id={TEST_ID_DISCLAIMER_BUTTON}
                            {...mkDisclaimerBtnTrackAttrs()}>
                            Disclaimer
                        </SettingsButton>
                        <SettingsButton
                            type="button"
                            aria-haspopup="dialog"
                            onClick={() => setIsAttributionOpen(true)}
                            data-test-id={TEST_ID_ATTRIBUTION_BUTTON}
                            {...mkAttributionBtnTrackAttrs()}>
                            Attribution
                        </SettingsButton>
                        <SettingsLink
                            href="https://allenai.org/privacy-policy"
                            target="_blank"
                            rel="noopener noreferrer"
                            data-test-id={TEST_ID_PRIVACY_POLICY_LINK}
                            {...mkPrivacyLinkTrackAttrs()}>
                            Privacy Policy
                        </SettingsLink>
                        <SettingsLink
                            href="https://allenai.org/terms"
                            target="_blank"
                            rel="noopener noreferrer"
                            data-test-id={TEST_ID_TERMS_OF_USE_LINK}
                            {...mkTosLinkTrackAttrs()}>
                            Terms of Use
                        </SettingsLink>
                        <SettingsLink
                            href="https://allenai.org/responsible-use"
                            target="_blank"
                            rel="noopener noreferrer"
                            data-test-id={TEST_ID_RESPONSIBLE_USE_LINK}
                            {...mkResponsibleUseLinkTrackAttrs()}>
                            Responsible Use
                        </SettingsLink>
                    </>
                )}
            </LinksSection>

            {layout === 'menu' && (
                <LinksSection>
                    <SettingsButton
                        type="button"
                        aria-haspopup="dialog"
                        onClick={() => setIsDisclaimerOpen(true)}
                        data-test-id={TEST_ID_DISCLAIMER_BUTTON}
                        {...mkDisclaimerBtnTrackAttrs()}>
                        Disclaimer
                    </SettingsButton>
                    <SettingsButton
                        type="button"
                        aria-haspopup="dialog"
                        onClick={() => setIsAttributionOpen(true)}
                        data-test-id={TEST_ID_ATTRIBUTION_BUTTON}
                        {...mkAttributionBtnTrackAttrs()}>
                        Attribution
                    </SettingsButton>
                    <SettingsLink
                        href="https://allenai.org/privacy-policy"
                        target="_blank"
                        rel="noopener noreferrer"
                        data-test-id={TEST_ID_PRIVACY_POLICY_LINK}
                        {...mkPrivacyLinkTrackAttrs()}>
                        Privacy Policy
                    </SettingsLink>
                    <SettingsLink
                        href="https://allenai.org/terms"
                        target="_blank"
                        rel="noopener noreferrer"
                        data-test-id={TEST_ID_TERMS_OF_USE_LINK}
                        {...mkTosLinkTrackAttrs()}>
                        Terms of Use
                    </SettingsLink>
                    <SettingsLink
                        href="https://allenai.org/responsible-use"
                        target="_blank"
                        rel="noopener noreferrer"
                        data-test-id={TEST_ID_RESPONSIBLE_USE_LINK}
                        {...mkResponsibleUseLinkTrackAttrs()}>
                        Responsible Use
                    </SettingsLink>
                </LinksSection>
            )}

            <DisclaimerDialog
                isOpen={isDisclaimerOpen}
                onClose={() => setIsDisclaimerOpen(false)}
            />
            <AttributionDialog
                isOpen={isAttributionOpen}
                onClose={() => setIsAttributionOpen(false)}
            />
        </>
    );
};

const LinksSection = styled('div')`
    align-self: stretch;
    display: flex;
    flex-direction: column;
    padding: ${({ theme }) => theme.spacing(0.5)};

    & + & {
        border-top: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }
`;

const linkBaseStyles = (theme: Theme) => ({
    background: 'none',
    border: 'none',
    color: theme.color['cream-100'].hex,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: '14px',
    padding: theme.spacing(1.5),
    textAlign: 'left' as const,
    textDecoration: 'none',
    transition: 'color 250ms ease-in-out',

    '&:hover, &:focus-visible': {
        color: theme.color['cream-60'].rgba.toString(),
    },
});

const SettingsLink = styled('a')(({ theme }) => linkBaseStyles(theme));

const SettingsButton = styled('button')(({ theme }) => linkBaseStyles(theme));
