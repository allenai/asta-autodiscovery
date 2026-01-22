'use client';

import { Box, CircularProgress, Alert, styled } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';
import { IntroBox } from '@/runs/components/IntroBox';
import { ExamplesRunsBox } from '@/runs/components/ExamplesBox';
import { ViewerRunsBox } from '@/runs/components/ViewerRunsBox';

/**
 * Main /runs page - shows welcome message when no run is selected
 */
export default function RunsPage() {
    const { isAuthenticated, isLoading } = useAuth0();

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100%',
                }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">Please log in to create and manage runs.</Alert>
            </Box>
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
        </Layout>
    );
}

const Layout = styled(Box)(({ theme }) => ({
    display: 'flex',
    flexDirection: 'column',
    gap: theme.spacing(4),
    padding: theme.spacing(4),
    maxWidth: '900px',
    margin: '0 auto',
}));

const Section = styled(Box)(({ theme }) => ({
    padding: theme.spacing(3),
}));
