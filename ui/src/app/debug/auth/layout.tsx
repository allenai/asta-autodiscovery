'use client';

import { Box, Grid, styled } from '@mui/material';

/**
 * Layout for runs pages - shows RunsList in sidebar consistently across all /runs routes
 */
export default function DebugAuthLayout({ children }: { children: React.ReactNode }) {
    return (
        <Wrapper>
            <Grid container sx={{ height: '100%' }}>
                {/* Main content */}
                <MainContent
                    item
                    xs={12}
                    md={10}
                    sx={{
                        height: '100%',
                        overflow: 'auto',
                    }}>
                    {children}
                </MainContent>
            </Grid>
        </Wrapper>
    );
}

const Wrapper = styled(Box)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    display: flex;
    height: 100vh;
    overflow: hidden;
`;

const MainContent = styled(Grid)`
    height: 100%;
    overflow: auto;
`;
