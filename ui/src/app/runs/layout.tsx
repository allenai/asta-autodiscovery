'use client';

import { Box, Grid, styled } from '@mui/material';

import { useRouter, usePathname } from 'next/navigation';

import RunsList from './components/RunsList';
import { IconAutoDSLogo } from '@/icons/Logo';
import Header from '@/components/Header';
import { RunsContextProvider } from '@/contexts/RunsContext';

/**
 * Layout for runs pages - shows RunsList in sidebar consistently across all /runs routes
 */
export default function RunsLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();

    // Extract runId from pathname if we're on a run detail page
    const runIdMatch = pathname.match(/^\/runs\/([^/]+)/);
    const selectedRunId = runIdMatch ? runIdMatch[1] : null;

    const handleRunCreated = (runid: string) => {
        router.push(`/runs/${runid}`);
    };

    const handleSelectRun = (runid: string) => {
        router.push(`/runs/${runid}`);
    };

    return (
        <RunsContextProvider>
            <Wrapper>
                <Grid container sx={{ height: '100%' }}>
                    {/* Sidebar - RunsList */}
                    <Sidebar item xs={12} md={2}>
                        <Logo>
                            <IconAutoDSLogo />
                        </Logo>
                        <RunsList
                            selectedRunId={selectedRunId}
                            onSelectRun={handleSelectRun}
                            onRunCreated={handleRunCreated}
                        />
                    </Sidebar>

                    {/* Main content */}
                    <MainContent
                        item
                        xs={12}
                        md={10}
                        sx={{
                            height: '100%',
                            overflow: 'auto',
                        }}>
                        <Header />
                        {children}
                    </MainContent>
                </Grid>
            </Wrapper>
        </RunsContextProvider>
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

    svg {
        width: 100%;
        height: auto;
    }
`;
