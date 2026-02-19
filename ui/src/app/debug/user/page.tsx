'use client';

import { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    CircularProgress,
    Alert,
    Chip,
    Avatar,
    styled,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import LockIcon from '@mui/icons-material/Lock';
import VerifiedIcon from '@mui/icons-material/Verified';

import { getUserApi } from '@/api/UserApi';
import { useAuth0 } from '@/contexts/Auth0Context';
import MetricCard from '@/metrics/components/MetricCard';
import type {
    GetViewerUserResponseBody,
    GetViewerEnrollmentResponseBody,
    GetViewerCreditsResponseBody,
} from '@/api/UserApi';

export default function DebugUserPage() {
    return (
        <Wrapper>
            <Typography variant="h1">User Debug</Typography>
            <UserProfileSection />
            <EnrollmentSection />
            <CreditsSection />
        </Wrapper>
    );
}

function UserProfileSection() {
    const userApi = getUserApi();
    const { isAuthenticated } = useAuth0();
    const [data, setData] = useState<GetViewerUserResponseBody | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (!isAuthenticated) {
                setLoading(false);
                return;
            }

            setLoading(true);
            setError(null);

            try {
                const { data: responseData } = await userApi.getViewer();
                setData(responseData);
            } catch (err) {
                console.error('Error fetching user profile:', err);
                setError(err instanceof Error ? err.message : 'Failed to load user profile');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isAuthenticated]);

    if (loading) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                </CardContent>
            </Card>
        );
    }

    if (!isAuthenticated) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        User Profile
                    </Typography>
                    <Alert severity="info">Please log in to view this information.</Alert>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        User Profile
                    </Typography>
                    <Alert severity="error">{error}</Alert>
                </CardContent>
            </Card>
        );
    }

    if (data?.user) {
        const { user } = data;
        return (
            <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'success.main' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <CheckCircleIcon sx={{ mr: 1, color: 'success.main' }} />
                        <Typography variant="h6">User Profile</Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        {user.picture && (
                            <Avatar
                                src={user.picture}
                                alt={user.name}
                                sx={{ width: 48, height: 48, mr: 2 }}
                            />
                        )}
                        <Box>
                            <Typography variant="body1" sx={{ fontWeight: 600 }}>
                                {user.name}
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="body2" color="text.secondary">
                                    {user.email}
                                </Typography>
                                {user.email_verified && (
                                    <VerifiedIcon sx={{ fontSize: 16, color: 'success.main' }} />
                                )}
                            </Box>
                        </Box>
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                User ID:
                            </Typography>
                            <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {user.sub}
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Email Verified:
                            </Typography>
                            <Typography variant="body2">
                                {user.email_verified ? 'Yes' : 'No'}
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        );
    }

    return null;
}

function EnrollmentSection() {
    const userApi = getUserApi();
    const { isAuthenticated } = useAuth0();
    const [data, setData] = useState<GetViewerEnrollmentResponseBody | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [permissionDenied, setPermissionDenied] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            if (!isAuthenticated) {
                setLoading(false);
                return;
            }

            setLoading(true);
            setError(null);
            setPermissionDenied(false);

            try {
                const { response, data: responseData } = await userApi.getViewerEnrollmentStatus();
                if (response.status === 403) {
                    setPermissionDenied(true);
                    const errorData = await response.json();
                    setError(errorData.error || 'Access denied');
                } else if (!response.ok) {
                    throw new Error('Failed to fetch enrollment status');
                } else if (responseData) {
                    setData(responseData);
                }
            } catch (err) {
                console.error('Error fetching enrollment status:', err);
                setError(err instanceof Error ? err.message : 'Failed to load enrollment status');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isAuthenticated]);

    if (loading) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                </CardContent>
            </Card>
        );
    }

    if (!isAuthenticated) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        Enrollment Status
                    </Typography>
                    <Alert severity="info">Please log in to view this information.</Alert>
                </CardContent>
            </Card>
        );
    }

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

    if (data) {
        return (
            <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'success.main' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <CheckCircleIcon sx={{ mr: 1, color: 'success.main' }} />
                        <Typography variant="h6">Enrollment Status</Typography>
                        {data.status && (
                            <Chip
                                label={data.status.toUpperCase()}
                                color="success"
                                size="small"
                                sx={{ ml: 2 }}
                            />
                        )}
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Enrolled:
                            </Typography>
                            <Typography variant="body2">{data.enrolled ? 'Yes' : 'No'}</Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Enrollment Date:
                            </Typography>
                            <Typography variant="body2">{data.enrollment_date || 'N/A'}</Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                Experiments Completed:
                            </Typography>
                            <Typography variant="body2">
                                {data.experiments_count ?? 'N/A'}
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">
                                User ID:
                            </Typography>
                            <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {data.user_id || 'N/A'}
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        );
    }

    return null;
}

function CreditsSection() {
    const userApi = getUserApi();
    const { isAuthenticated } = useAuth0();
    const [data, setData] = useState<GetViewerCreditsResponseBody | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (!isAuthenticated) {
                setLoading(false);
                return;
            }

            setLoading(true);
            setError(null);

            try {
                const { data: responseData } = await userApi.getViewerCredits();
                setData(responseData);
            } catch (err) {
                console.error('Error fetching credits:', err);
                setError(err instanceof Error ? err.message : 'Failed to load credits');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isAuthenticated]);

    if (loading) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                </CardContent>
            </Card>
        );
    }

    if (!isAuthenticated) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        Credits Information
                    </Typography>
                    <Alert severity="info">Please log in to view this information.</Alert>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                        Credits Information
                    </Typography>
                    <Alert severity="error">{error}</Alert>
                </CardContent>
            </Card>
        );
    }

    if (data?.credits) {
        const { credits } = data;
        return (
            <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'info.main' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Credits Information</Typography>
                    </Box>

                    <DarkContainer>
                        <CreditsGrid>
                            <MetricCard value={credits.granted} label="GRANTED" />
                            <MetricCard value={credits.consumed} label="CONSUMED" />
                            <MetricCard value={credits.pending} label="PENDING" />
                            <MetricCard value={credits.available} label="AVAILABLE" />
                        </CreditsGrid>
                    </DarkContainer>
                </CardContent>
            </Card>
        );
    }

    return null;
}

const Wrapper = styled('div')`
    background-color: ${({ theme }) => theme.color['cream-100'].hex};
    padding: ${({ theme }) => theme.spacing(3)};
`;

const DarkContainer = styled(Box)`
    background: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    padding: ${({ theme }) => theme.spacing(2)};
    border-radius: 8px;
`;

const CreditsGrid = styled(Box)`
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: ${({ theme }) => theme.spacing(1.5)};
`;
