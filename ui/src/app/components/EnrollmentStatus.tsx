'use client';

import { useEffect, useState } from 'react';
import { Box, Typography, Card, CardContent, CircularProgress, Alert, Chip } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import { useAuth0 } from '../contexts/Auth0Context';

interface EnrollmentData {
    enrolled: boolean;
    enrollment_date: string;
    status: string;
    experiments_count: number;
    user_id: string;
}

export default function EnrollmentStatus() {
    const { isAuthenticated, isLoading: authLoading, getAccessToken } = useAuth0();
    const [enrollmentData, setEnrollmentData] = useState<EnrollmentData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [permissionDenied, setPermissionDenied] = useState(false);

    useEffect(() => {
        const fetchEnrollmentStatus = async () => {
            if (!isAuthenticated) {
                return;
            }

            setLoading(true);
            setError(null);
            setPermissionDenied(false);

            try {
                const token = await getAccessToken();
                const response = await fetch('/api/enrollment-status', {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (response.status === 403) {
                    // Permission denied
                    setPermissionDenied(true);
                    const errorData = await response.json();
                    setError(errorData.error || 'Access denied');
                } else if (!response.ok) {
                    throw new Error('Failed to fetch enrollment status');
                } else {
                    const data = await response.json();
                    setEnrollmentData(data);
                }
            } catch (err) {
                console.error('Error fetching enrollment status:', err);
                setError(err instanceof Error ? err.message : 'Failed to load enrollment status');
            } finally {
                setLoading(false);
            }
        };

        fetchEnrollmentStatus();
    }, [isAuthenticated, getAccessToken]);

    if (authLoading || loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return null;
    }

    // Permission Denied State
    if (permissionDenied) {
        return (
            <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'warning.main' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <LockIcon sx={{ mr: 1, color: 'warning.main' }} />
                        <Typography variant="h6">Enrollment Status</Typography>
                    </Box>
                    <Alert severity="warning">
                        <Typography variant="body2" sx={{ mb: 1 }}>
                            <strong>Permission Required</strong>
                        </Typography>
                        <Typography variant="body2">
                            You do not have permission to view enrollment status. This feature
                            requires the <code>enroll:autodiscovery_v0</code> permission.
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 1 }}>
                            Contact your administrator to request access.
                        </Typography>
                    </Alert>
                </CardContent>
            </Card>
        );
    }

    // Error State
    if (error && !permissionDenied) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        Enrollment Status
                    </Typography>
                    <Alert severity="error">{error}</Alert>
                </CardContent>
            </Card>
        );
    }

    // Success State - User has permission
    if (enrollmentData) {
        return (
            <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'success.main' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <CheckCircleIcon sx={{ mr: 1, color: 'success.main' }} />
                        <Typography variant="h6">Enrollment Status</Typography>
                        <Chip
                            label={enrollmentData.status.toUpperCase()}
                            color="success"
                            size="small"
                            sx={{ ml: 2 }}
                        />
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Enrolled:
                            </Typography>
                            <Typography variant="body2">
                                {enrollmentData.enrolled ? 'Yes' : 'No'}
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Enrollment Date:
                            </Typography>
                            <Typography variant="body2">
                                {enrollmentData.enrollment_date}
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Experiments Completed:
                            </Typography>
                            <Typography variant="body2">
                                {enrollmentData.experiments_count}
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                User ID:
                            </Typography>
                            <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {enrollmentData.user_id}
                            </Typography>
                        </Box>
                    </Box>

                    <Alert severity="info" sx={{ mt: 2 }}>
                        This data is protected by the <code>enroll:autodiscovery_v0</code>{' '}
                        permission. Only authorized users can view this information.
                    </Alert>
                </CardContent>
            </Card>
        );
    }

    return null;
}
