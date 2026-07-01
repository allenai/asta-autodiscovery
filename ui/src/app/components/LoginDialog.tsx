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
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <TextField
                        label="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        fullWidth
                        autoComplete="username"
                    />
                    <TextField
                        label="Password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        fullWidth
                        autoComplete="current-password"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={onClose} disabled={submitting}>
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        variant="contained"
                        disabled={submitting || !username || !password}>
                        {submitting ? 'Signing in…' : 'Sign in'}
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
