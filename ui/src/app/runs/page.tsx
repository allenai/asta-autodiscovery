'use client';

import { Box, Typography, Paper, CircularProgress, Alert } from '@mui/material';
import { useAuth0 } from '@/app/contexts/Auth0Context';

/**
 * Main /runs page - shows welcome message when no run is selected
 */
export default function RunsPage() {
  const { isAuthenticated, isLoading, user } = useAuth0();

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
      }}
    >
      <Paper sx={{ p: 4, maxWidth: 'sm', textAlign: 'center' }}>
        <Typography variant="h5" gutterBottom>
          Welcome to Autodiscovery Runs
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Create a new run or select an existing run from the sidebar to get started.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {user?.name && `Logged in as: ${user.name}`}
        </Typography>
      </Paper>
    </Box>
  );
}
