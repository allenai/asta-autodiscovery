'use client';

import { Box, Grid } from '@mui/material';
import RunsList from './components/RunsList';
import { useRouter, usePathname } from 'next/navigation';

/**
 * Layout for runs pages - shows RunsList in sidebar consistently across all /runs routes
 */
export default function RunsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  // Extract runId from pathname if we're on a run detail page
  const runIdMatch = pathname.match(/^\/runs\/([^\/]+)/);
  const selectedRunId = runIdMatch ? runIdMatch[1] : null;

  const handleRunCreated = (runid: string) => {
    router.push(`/runs/${runid}`);
  };

  const handleSelectRun = (runid: string) => {
    router.push(`/runs/${runid}`);
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Grid container sx={{ height: '100%' }}>
        {/* Sidebar - RunsList */}
        <Grid
          item
          xs={12}
          md={3}
          sx={{
            height: '100%',
            overflow: 'auto',
            borderRight: 1,
            borderColor: 'divider',
          }}
        >
          <RunsList
            selectedRunId={selectedRunId}
            onSelectRun={handleSelectRun}
            onRunCreated={handleRunCreated}
          />
        </Grid>

        {/* Main content */}
        <Grid
          item
          xs={12}
          md={9}
          sx={{
            height: '100%',
            overflow: 'auto',
            bgcolor: 'grey.50',
          }}
        >
          {children}
        </Grid>
      </Grid>
    </Box>
  );
}
