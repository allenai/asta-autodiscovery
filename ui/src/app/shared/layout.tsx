'use client';

import { Box, styled } from '@mui/material';
import { useRouter } from 'next/navigation';

import RunsList from '@/runs/components/RunsList';
import { IconAutoDSLogo } from '@/icons/Logo';
import Header from '@/components/Header';
import { RunsContextProvider } from '@/contexts/RunsContext';
import { ToS } from '@/components/ToS';

/**
 * Layout for shared runs pages - same structure as runs layout but for viewing
 * runs shared by other users.
 */
export default function SharedLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();

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
                        <ScrollArea>
                            <ScrollContainer>
                                <ScrollContent>
                                    <RunsList
                                        selectedRunId={null}
                                        onSelectRun={handleSelectRun}
                                    />
                                </ScrollContent>
                            </ScrollContainer>
                        </ScrollArea>
                        <ToS />
                    </Sidebar>

                    {/* Main content */}
                    <MainContent>
                        <Header />
                        <ScrollArea>
                            <ScrollContainer>
                                <ScrollContent>{children}</ScrollContent>
                            </ScrollContainer>
                        </ScrollArea>
                    </MainContent>
                </Layout>
            </Wrapper>
        </RunsContextProvider>
    );
}

const Wrapper = styled(Box)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    position: absolute;
    inset: 0;
`;

const Layout = styled('div')`
    display: grid;
    height: 100%;
    grid-template-columns: 1fr 5fr;
    grid-template-areas: 'sidebar main-content';

    @media (max-width: 900px) {
        grid-template-columns: 1fr;
        grid-template-rows: auto 1fr;
        grid-template-areas: 'sidebar' 'main-content';
    }

    @media (min-width: 1600px) {
        grid-template-columns: 266px 1fr;
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
    padding: ${({ theme }) => theme.spacing(2, 2, 0, 2)};

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
`;
