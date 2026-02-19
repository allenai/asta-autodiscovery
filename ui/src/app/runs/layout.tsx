'use client';

import { Box, styled } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';

import RunsList from './components/RunsList';
import { IconAutoDSLogo } from '@/icons/Logo';
import Header from '@/components/Header';
import { ToS } from '@/components/ToS';
import { useAuth0 } from '@/contexts/Auth0Context';
import { mkLogoTrackAttrs } from '@/analytics/run';
import { scrollbarStyles } from '@/utils/scrollbar';

/**
 * Layout for runs pages - shows RunsList in sidebar consistently across all /runs routes
 */
export default function RunsLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const { isAuthenticated } = useAuth0();

    // Extract runId from pathname if we're on a run detail page
    const runIdMatch = pathname.match(/^\/runs\/([^/]+)/);
    const selectedRunId = runIdMatch ? runIdMatch[1] : null;

    const handleSelectRun = (runid: string) => {
        router.push(`/runs/${runid}`);
    };

    return (
        <Wrapper $isAuthenticated={isAuthenticated} $isRunsHome={pathname === '/runs'}>
            <Layout $showSidebar={isAuthenticated}>
                {/* Sidebar - RunsList */}
                {isAuthenticated && (
                    <Sidebar>
                        <Logo href="/runs" {...mkLogoTrackAttrs()}>
                            <IconAutoDSLogo />
                        </Logo>
                        <ScrollArea>
                            <ScrollContainer>
                                <ScrollContent>
                                    <RunsList
                                        selectedRunId={selectedRunId}
                                        onSelectRun={handleSelectRun}
                                    />
                                </ScrollContent>
                            </ScrollContainer>
                        </ScrollArea>
                        <ToS />
                    </Sidebar>
                )}

                {/* Main content */}
                <MainContent>
                    {isAuthenticated && <Header />}
                    {!isAuthenticated && pathname.startsWith('/shared') && (
                        <Header showBackButton />
                    )}
                    <ScrollArea>
                        <ScrollContainer>
                            <ScrollContent>{children}</ScrollContent>
                        </ScrollContainer>
                    </ScrollArea>
                </MainContent>
            </Layout>
        </Wrapper>
    );
}

const Wrapper = styled('div')<{ $isAuthenticated: boolean; $isRunsHome: boolean }>`
    background: ${({ theme, $isAuthenticated, $isRunsHome }) => {
        const gradient = `radial-gradient(141.38% 60.74% at 50% 113.89%, #245555 0%, rgba(36, 85, 85, 0.20) 50%, rgba(36, 85, 85, 0.00) 100%)`;
        const fallbackColor = theme.color['extra-dark-teal-100'].hex;

        if (!$isAuthenticated && $isRunsHome) {
            return `url(/autods-bg.png), ${gradient}, ${fallbackColor}`;
        }
        return `${gradient}, ${fallbackColor}`;
    }};
    ${({ $isAuthenticated, $isRunsHome }) =>
        !$isAuthenticated &&
        $isRunsHome &&
        `
        background-position: bottom right, center, center;
        background-repeat: no-repeat, no-repeat, no-repeat;
        background-size: contain, cover, cover;
    `}
    position: absolute;
    inset: 0;
`;

const Layout = styled('div')<{ $showSidebar: boolean }>`
    display: grid;
    height: 100%;
    grid-template-columns: ${({ $showSidebar }) => ($showSidebar ? '1fr 5fr' : '1fr')};
    grid-template-areas: ${({ $showSidebar }) =>
        $showSidebar ? "'sidebar main-content'" : "'main-content'"};

    @media (max-width: 900px) {
        grid-template-columns: 1fr;
        grid-template-rows: ${({ $showSidebar }) => ($showSidebar ? 'auto 1fr' : '1fr')};
        grid-template-areas: ${({ $showSidebar }) =>
            $showSidebar ? "'sidebar' 'main-content'" : "'main-content'"};
    }

    @media (min-width: 1600px) {
        grid-template-columns: ${({ $showSidebar }) => ($showSidebar ? '266px 1fr' : '1fr')};
    }
`;

const Sidebar = styled('div')`
    background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    border-right: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    display: flex;
    flex-direction: column;
    grid-area: sidebar;
`;

const MainContent = styled('div')`
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    grid-area: main-content;
    min-width: 0;
`;

const Logo = styled('a')`
    padding: ${({ theme }) => theme.spacing(2)};

    svg {
        width: 100%;
        min-width: 175px;
        max-width: 300px;
        height: auto;
    }
`;

const ScrollArea = styled(Box)`
    flex: 1 1 auto;
    position: relative;
`;

const ScrollContainer = styled('div')`
    position: absolute;
    inset: 0;
`;

const ScrollContent = styled('div')`
    height: 100%;
    overflow: auto;
    ${({ theme }) => scrollbarStyles(theme)}
`;
