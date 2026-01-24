'use client';

import { Box, styled } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';

import RunsList from './components/RunsList';
import { IconAutoDSLogo } from '@/icons/Logo';
import Header from '@/components/Header';
import { RunsContextProvider } from '@/contexts/RunsContext';
import { ToS } from '@/components/ToS';

/**
 * Layout for runs pages - shows RunsList in sidebar consistently across all /runs routes
 */
export default function RunsLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();

    // Extract runId from pathname if we're on a run detail page
    const runIdMatch = pathname.match(/^\/runs\/([^/]+)/);
    const selectedRunId = runIdMatch ? runIdMatch[1] : null;

    const handleSelectRun = (runid: string) => {
        router.push(`/runs/${runid}`);
    };

    return (
        <RunsContextProvider>
            <Wrapper>
                <Layout>
                    {/* Sidebar - RunsList */}
                    <Sidebar>
                        <Logo href="/runs">
                            <IconAutoDSLogo />
                        </Logo>
                        <RunsList selectedRunId={selectedRunId} onSelectRun={handleSelectRun} />
                        <ToS />
                    </Sidebar>

                    {/* Main content */}
                    <MainContent>
                        <Header />
                        {children}
                    </MainContent>
                </Layout>
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

const Layout = styled('div')`
    display: grid;
    grid-template-columns: 1fr 5fr;
    grid-template-areas: 'sidebar main-content';
`;

const Sidebar = styled('div')`
    background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    border-right: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    display: flex;
    flex-direction: column;
    grid-area: sidebar;
    height: 100%;
    overflow: auto;
`;

const MainContent = styled('div')`
    flex-grow: 1;
    grid-area: main-content;
    min-width: 0;
`;

const Logo = styled('a')`
    padding: ${({ theme }) => theme.spacing(2, 2, 0, 2)};

    svg {
        width: 100%;
        height: auto;
    }
`;
