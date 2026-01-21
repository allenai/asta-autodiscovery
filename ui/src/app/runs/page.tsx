'use client';

import { Box, Typography, CircularProgress, Alert, styled } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';

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
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
                p: 3,
            }}>
            <IntroBox>
                <IntroTitle>AutoDiscovery</IntroTitle>
                Uncover surprising insights hidden in your data. AutoDiscovery uses Bayesian
                surprise (a measure of how much a finding shifts our beliefs) to autonomously
                explore your datasets and identify discoveries that genuinely change what we know,
                not just what's obvious or diverse.
            </IntroBox>
        </Box>
    );
}

const IntroBox = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    padding: theme.spacing(3),
}));

const IntroTitle = styled(Typography)(({ theme }) => ({
    color: theme.color['green-100'].hex,
    fontSize: '2.5rem',
    fontWeight: 'bold',
}));
