'use client';

import { Box, Grid, styled } from '@mui/material';

import { IconAutoDSLogo } from '@/icons/Logo';
import Header from '@/components/Header';

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

const Sidebar = styled(Grid)`
    background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    border-right: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: auto;
`;

const MainContent = styled(Grid)`
    height: 100%;
    overflow: auto;
`;

const Logo = styled('div')`
    padding: ${({ theme }) => theme.spacing(2)};
`;
