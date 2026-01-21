'use client';

import { useEffect, useState } from 'react';
import { Box, Typography, Avatar, CircularProgress, Alert } from '@mui/material';

import { getUserApi } from '@/api/UserApi';
import { useAuth0 } from '@/contexts/Auth0Context';
import { User, getUserFromApi } from '@/types/User';

export default function UserProfile() {
    const userApi = getUserApi();

    const { isAuthenticated, isLoading } = useAuth0();
    const [userData, setUserData] = useState<User | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loadingUser, setLoadingUser] = useState(false);

    useEffect(() => {
        const fetchUserData = async () => {
            if (!isAuthenticated) {
                return;
            }

            setLoadingUser(true);
            setError(null);

            try {
                const { data } = await userApi.getViewer();
                setUserData(getUserFromApi(data.user));
            } catch (err) {
                console.error('Error fetching user data:', err);
                setError(err instanceof Error ? err.message : 'Failed to load user data');
            } finally {
                setLoadingUser(false);
            }
        };

        fetchUserData();
    }, [isAuthenticated]);

    if (isLoading || loadingUser) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography>Please log in to view your profile.</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">{error}</Alert>
            </Box>
        );
    }

    if (!userData) {
        return null;
    }

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Avatar
                    src={userData.picture}
                    alt={userData.name}
                    sx={{ width: 80, height: 80, mr: 2 }}
                />
                <Box>
                    <Typography variant="h5">{userData.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                        {userData.email}
                    </Typography>
                    {userData.emailVerified && (
                        <Typography variant="caption" color="success.main">
                            ✓ Verified
                        </Typography>
                    )}
                </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                    User ID: {userData.sub}
                </Typography>
            </Box>
        </Box>
    );
}
