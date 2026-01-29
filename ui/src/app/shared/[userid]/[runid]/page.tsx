'use client';

import { Box, Alert } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunStatus from '@/runs/components/RunStatus';

interface SharedRunPageProps {
    params: {
        userid: string;
        runid: string;
    };
}

/**
 * Page for viewing shared/public runs from other users.
 * These runs are read-only - no setup or cancel actions allowed.
 */
export default function SharedRunPage({ params }: SharedRunPageProps) {
    const { isAuthenticated, isLoading } = useAuth0();
    const { userid, runid } = params;

    if (isLoading) {
        return <LoadingSpinner />;
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">Please log in to view this run.</Alert>
            </Box>
        );
    }

    return <RunStatus runid={runid} userid={userid} />;
}
