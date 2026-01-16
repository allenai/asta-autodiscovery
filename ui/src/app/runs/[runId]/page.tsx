'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
import { useAuth0 } from '@/app/contexts/Auth0Context';
import { getRun } from '../actions';
import RunSetup from '../components/RunSetup';
import RunStatus from '../components/RunStatus';
import { useRouter } from 'next/navigation';

interface RunPageProps {
  params: {
    runId: string;
  };
}

/**
 * Individual run page - shows RunSetup or RunStatus based on run state
 */
export default function RunPage({ params }: RunPageProps) {
  const { isAuthenticated, isLoading, getAccessToken } = useAuth0();
  const router = useRouter();
  const runId = params.runId;

  const [checkingRun, setCheckingRun] = useState(true);
  const [runState, setRunState] = useState<'setup' | 'submitted'>('setup');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkRunStatus = async () => {
      if (!isAuthenticated) return;

      setCheckingRun(true);
      setError(null);

      try {
        const token = await getAccessToken();
        const runData = await getRun(runId, token);

        // Check if run has been submitted
        if (
          runData.run_details?.execution_id ||
          (runData.run_details?.status && runData.run_details.status.toUpperCase() !== 'CREATED')
        ) {
          setRunState('submitted');
        } else {
          setRunState('setup');
        }
      } catch (err) {
        console.error('Error loading run:', err);
        setError(err instanceof Error ? err.message : 'Failed to load run');
        setRunState('setup');
      } finally {
        setCheckingRun(false);
      }
    };

    checkRunStatus();
  }, [runId, isAuthenticated, getAccessToken]);

  const handleSubmitSuccess = () => {
    setRunState('submitted');
  };

  const handleRunCancelled = () => {
    router.push('/runs');
  };

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please log in to view this run.</Alert>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Box>
    );
  }

  if (checkingRun) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
          p: 3,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <>
      {runState === 'setup' && <RunSetup runid={runId} onSubmitSuccess={handleSubmitSuccess} />}
      {runState === 'submitted' && <RunStatus runid={runId} onRunCancelled={handleRunCancelled} />}
    </>
  );
}
