import { Box, CircularProgress } from '@mui/material';

/**
 * Full-page centered loading spinner.
 */
export const LoadingSpinner = () => {
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
};
