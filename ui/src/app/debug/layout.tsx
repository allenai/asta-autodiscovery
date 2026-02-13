'use client';

import { Box, styled } from '@mui/material';
import { scrollbarStyles } from '@/utils/scrollbar';

/**
 * Layout for debug pages
 */
export default function DebugLayout({ children }: { children: React.ReactNode }) {
    return (
        <ScrollContainer>
            <ScrollableArea>{children}</ScrollableArea>
        </ScrollContainer>
    );
}

const ScrollContainer = styled(Box)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    position: absolute;
    inset: 0;
`;

const ScrollableArea = styled('div')`
    height: 100%;
    overflow: auto;
    ${({ theme }) => scrollbarStyles(theme)}
`;
