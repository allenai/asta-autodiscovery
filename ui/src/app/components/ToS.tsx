import { Box, Link, styled } from '@mui/material';
import { useState } from 'react';

import { DisclaimerDialog } from './DisclaimerDialog';
import { AttributionDialog } from './AttributionDialog';
import {
    mkAttributionBtnTrackAttrs,
    mkDisclaimerBtnTrackAttrs,
    mkPrivacyLinkTrackAttrs,
    mkResponsibleUseLinkTrackAttrs,
    mkTosLinkTrackAttrs,
} from '@/analytics/run';
import {
    TEST_ID_ATTRIBUTION_BUTTON,
    TEST_ID_DISCLAIMER_BUTTON,
    TEST_ID_PRIVACY_POLICY_LINK,
    TEST_ID_RESPONSIBLE_USE_LINK,
    TEST_ID_TERMS_OF_USE_LINK,
} from '@/testIds';

export const ToS = () => {
    const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
    const [isAttributionOpen, setIsAttributionOpen] = useState(false);

    return (
        <>
            <TosWrapper>
                <MobileFeedbackLink
                    href="https://docs.google.com/forms/d/e/1FAIpQLScmKqOj9EuOrfNlO0ySm_5ITPH80anDgC3FDBuSEeesgztv1Q/viewform"
                    target="_blank"
                    rel="noopener noreferrer">
                    Feedback
                </MobileFeedbackLink>
                <Link
                    onClick={() => setIsDisclaimerOpen(true)}
                    data-test-id={TEST_ID_DISCLAIMER_BUTTON}
                    {...mkDisclaimerBtnTrackAttrs()}>
                    Disclaimer
                </Link>
                <Link
                    onClick={() => setIsAttributionOpen(true)}
                    data-test-id={TEST_ID_ATTRIBUTION_BUTTON}
                    {...mkAttributionBtnTrackAttrs()}>
                    Attribution
                </Link>
                <Link
                    href="https://allenai.org/privacy-policy"
                    target="_blank"
                    rel="noopener noreferrer"
                    data-test-id={TEST_ID_PRIVACY_POLICY_LINK}
                    {...mkPrivacyLinkTrackAttrs()}>
                    Privacy Policy
                </Link>
                <Link
                    href="https://allenai.org/terms"
                    target="_blank"
                    rel="noopener noreferrer"
                    data-test-id={TEST_ID_TERMS_OF_USE_LINK}
                    {...mkTosLinkTrackAttrs()}>
                    Terms of Use
                </Link>
                <Link
                    href="https://allenai.org/responsible-use"
                    target="_blank"
                    rel="noopener noreferrer"
                    data-test-id={TEST_ID_RESPONSIBLE_USE_LINK}
                    {...mkResponsibleUseLinkTrackAttrs()}>
                    Responsible Use
                </Link>
            </TosWrapper>
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

const MobileFeedbackLink = styled(Link)`
    display: none;

    @media (max-width: 600px) {
        display: inline;
    }
`;

const TosWrapper = styled(Box)(({ theme }) => ({
    borderTop: `1px solid ${theme.color['cream-10'].rgba.toString()}`,

    display: 'flex',
    flexWrap: 'wrap',
    gap: '2px 12px',
    padding: theme.spacing(2),

    a: {
        color: theme.color['cream-100'].hex,
        fontSize: '14px',

        '&:hover': {
            color: theme.color['cream-60'].rgba.toString(),
            cursor: 'pointer',
            transition: 'all 250ms ease-in-out',
        },
    },

    '@media (max-width: 600px)': {
        justifyContent: 'center',
    },
}));
