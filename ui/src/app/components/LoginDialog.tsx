'use client';

import { useState } from 'react';
import {
    Alert,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    TextField,
} from '@mui/material';

import {
    TEST_ID_LOGIN_ERROR,
    TEST_ID_LOGIN_PASSWORD,
    TEST_ID_LOGIN_SUBMIT,
    TEST_ID_LOGIN_USERNAME,
} from '@/testIds';

interface LoginDialogProps {
    open: boolean;
    onClose: () => void;
    onSubmit: (creds: { username: string; password: string }) => Promise<void>;
    error: string | null;
}

/** Username/password login modal used by the password_file auth provider. */
export default function LoginDialog({ open, onClose, onSubmit, error }: LoginDialogProps) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await onSubmit({ username, password });
            setPassword('');
        } catch {
            // Error surfaced via the `error` prop; keep the dialog open.
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
            <form onSubmit={handleSubmit}>
                <DialogTitle>Sign in</DialogTitle>
                {/*
                 * MUI zeroes padding-top on a DialogContent that directly follows a
                 * DialogTitle (via a higher-specificity `.MuiDialogTitle-root + &` rule),
                 * which clips the first field's floating label. Re-assert top padding at
                 * matching specificity so it actually applies.
                 */}
                <DialogContent
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                        '&.MuiDialogContent-root': { pt: 2 },
                    }}>
                    {error && (
                        <Alert severity="error" data-test-id={TEST_ID_LOGIN_ERROR}>
                            {error}
                        </Alert>
                    )}
                    <TextField
                        label="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        fullWidth
                        autoComplete="username"
                        inputProps={{ 'data-test-id': TEST_ID_LOGIN_USERNAME }}
                    />
                    <TextField
                        label="Password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        fullWidth
                        autoComplete="current-password"
                        inputProps={{ 'data-test-id': TEST_ID_LOGIN_PASSWORD }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={onClose} disabled={submitting}>
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        variant="contained"
                        disabled={submitting || !username || !password}
                        data-test-id={TEST_ID_LOGIN_SUBMIT}>
                        {submitting ? 'Signing in…' : 'Sign in'}
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
