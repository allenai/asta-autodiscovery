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

export const ToS = () => {
    const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
    const [isAttributionOpen, setIsAttributionOpen] = useState(false);

    return (
        <>
            <TosWrapper>
                <Link onClick={() => setIsDisclaimerOpen(true)} {...mkDisclaimerBtnTrackAttrs()}>
                    Disclaimer
                </Link>
                <Link onClick={() => setIsAttributionOpen(true)} {...mkAttributionBtnTrackAttrs()}>
                    Attribution
                </Link>
                <Link
                    href="https://allenai.org/privacy-policy"
                    target="_blank"
                    rel="noopener noreferrer"
                    {...mkPrivacyLinkTrackAttrs()}>
                    Privacy Policy
                </Link>
                <Link
                    href="https://allenai.org/terms"
                    target="_blank"
                    rel="noopener noreferrer"
                    {...mkTosLinkTrackAttrs()}>
                    Terms of Use
                </Link>
                <Link
                    href="https://allenai.org/responsible-use"
                    target="_blank"
                    rel="noopener noreferrer"
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
}));
