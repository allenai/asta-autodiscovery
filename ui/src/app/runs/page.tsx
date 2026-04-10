'use client';

import { Box, CircularProgress, styled, Typography } from '@mui/material';
import Image from 'next/image';

import { useAuth0 } from '@/contexts/Auth0Context';
import { TEST_ID_AI2_LOGO_LINK, TEST_ID_ASTA_LABS_LOGO_LINK } from '@/testIds';
import { IntroBox } from '@/runs/components/IntroBox';
import { ExamplesRunsBox } from '@/runs/components/ExamplesRunsBox';
import { ViewerRunsBox } from '@/runs/components/ViewerRunsBox';
import { ToS } from '@/components/ToS';
import { AstaAdBanner } from '@/components/AstaAdBanner';

/**
 * Main /runs page - shows welcome message when no run is selected
 */
export default function RunsPage() {
    const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100%',
                }}>
                <CircularProgress sx={(theme) => ({ color: theme.color['green-100'].hex })} />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return (
            <>
                <LoggedOutLayout>
                    <Section>
                        <IntroBox showLogin onLoginClick={loginWithRedirect} />
                        <Attribution>
                            AutoDiscovery is developed by{' '}
                            <Ai2LogoWrapper
                                href="https://allenai.org"
                                target="_blank"
                                rel="noopener noreferrer"
                                data-test-id={TEST_ID_AI2_LOGO_LINK}>
                                <Image
                                    src="/ai2-logo.svg"
                                    alt="Ai2"
                                    width={50}
                                    height={16}
                                    style={{ display: 'block' }}
                                />
                            </Ai2LogoWrapper>{' '}
                            and is an{' '}
                            <AstaLabsLogoWrapper
                                href="https://asta.example.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                data-test-id={TEST_ID_ASTA_LABS_LOGO_LINK}>
                                <Image
                                    src="/astalabs-logo.svg"
                                    alt="AstaLabs"
                                    width={120.004}
                                    height={17}
                                    style={{ display: 'block', transform: 'translateY(-2px)' }}
                                />
                            </AstaLabsLogoWrapper>{' '}
                            experiment.
                        </Attribution>
                    </Section>
                    <Section>
                        <ExamplesRunsBox />
                    </Section>
                    <FooterWrapper>
                        <ToS />
                    </FooterWrapper>
                </LoggedOutLayout>
                <AstaAdBanner isFullWidth />
            </>
        );
    }

    return (
        <Layout>
            <Section>
                <IntroBox />
            </Section>
            <Section>
                <ViewerRunsBox />
            </Section>
            <Section>
                <ExamplesRunsBox />
            </Section>
            <AstaAdBanner />
        </Layout>
    );
}

const Layout = styled(Box)(({ theme }) => ({
    display: 'flex',
    flexDirection: 'column',
    padding: theme.spacing(4),
    maxWidth: '900px',
    margin: '0 auto',

    '@media (max-width: 600px)': {
        padding: theme.spacing(3),
    },
}));

const LoggedOutLayout = styled(Box)(({ theme }) => ({
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    minHeight: '100%',
    padding: theme.spacing(4),
    maxWidth: '900px',
    margin: '0 auto',

    '@media (max-width: 600px)': {
        padding: theme.spacing(3),
    },
}));

const Section = styled(Box)(({ theme }) => ({
    padding: theme.spacing(3),

    '@media (max-width: 600px)': {
        padding: 0,
    },
}));

const FooterWrapper = styled(Box)(({ theme }) => ({
    '& > div': {
        borderTop: 'none',
    },
    '& a': {
        opacity: 0.8,
        '&:hover': {
            opacity: 1,
            color: `${theme.color['cream-100'].hex} !important`,
        },
    },
}));

const Attribution = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    opacity: 0.8,
    fontFamily: 'Manrope',
    fontSize: '0.875rem',
    textAlign: 'left',
    marginTop: theme.spacing(1),
    lineHeight: '1.5',

    '@media (max-width: 600px)': {
        lineHeight: '1.75',
        opacity: 1,
    },
}));

const Ai2LogoWrapper = styled('a')({
    display: 'inline-block',
    verticalAlign: 'middle',
    lineHeight: 0,
    margin: '0 4px',
    textDecoration: 'none',

    '@media (max-width: 600px)': {
        '& img': {
            height: '14px',
            width: 'auto',
        },
    },
});

const AstaLabsLogoWrapper = styled('a')({
    display: 'inline-block',
    verticalAlign: 'middle',
    lineHeight: 0,
    margin: '0 4px',
    textDecoration: 'none',

    '@media (max-width: 600px)': {
        '& img': {
            height: '14px',
            width: 'auto',
        },
    },
});
