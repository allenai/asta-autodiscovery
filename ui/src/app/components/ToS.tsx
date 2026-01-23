import { Box, Link, styled } from '@mui/material';
import { useState } from 'react';

import { DisclaimerDialog } from './DisclaimerDialog';
import { AttributionDialog } from './AttributionDialog';

export const ToS = () => {
    const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
    const [isAttributionOpen, setIsAttributionOpen] = useState(false);

    return (
        <>
            <TosWrapper>
                <Link onClick={() => setIsDisclaimerOpen(true)}>Disclaimer</Link>
                <Link onClick={() => setIsAttributionOpen(true)}>Attribution</Link>
                <Link
                    href="https://allenai.org/privacy-policy"
                    target="_blank"
                    rel="noopener noreferrer">
                    Privacy Policy
                </Link>
                <Link href="https://allenai.org/terms" target="_blank" rel="noopener noreferrer">
                    Terms of Use
                </Link>
                <Link
                    href="https://allenai.org/responsible-use"
                    target="_blank"
                    rel="noopener noreferrer">
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
    gap: theme.spacing(1.5),
    padding: theme.spacing(2),

    a: {
        color: theme.color['cream-100'].hex,
        fontSize: '0.875rem',

        '&:hover': {
            color: theme.color['cream-60'].rgba.toString(),
            cursor: 'pointer',
            transition: 'all 250ms ease-in-out',
        },
    },
}));
