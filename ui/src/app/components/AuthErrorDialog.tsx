'use client';

import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Button,
} from '@mui/material';

import { useAuth0 } from '../contexts/Auth0Context';

export default function AuthErrorDialog() {
    const { authError, logout, loginWithRedirect } = useAuth0();

    const handleClose = () => {
        // Log the user out and return to home page
        logout();
    };

    const handleTryAgain = () => {
        // Log out first, then login again
        logout();
        // Small delay to ensure logout completes before redirecting to login
        setTimeout(() => {
            loginWithRedirect();
        }, 500);
    };

    return (
        <Dialog open={!!authError} onClose={handleClose} disableEscapeKeyDown>
            <DialogTitle>Access Denied</DialogTitle>
            <DialogContent>
                <DialogContentText>You must be approved to access this app.</DialogContentText>
                <DialogContentText sx={{ mt: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
                    Please contact your administrator to request access.
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Close</Button>
                <Button onClick={handleTryAgain} variant="contained" color="primary">
                    Try Again
                </Button>
            </DialogActions>
        </Dialog>
    );
}
