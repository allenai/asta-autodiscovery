'use client';

import { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    CircularProgress,
    Alert,
    Avatar,
    Chip,
    styled,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import VerifiedIcon from '@mui/icons-material/Verified';
import VpnKeyIcon from '@mui/icons-material/VpnKey';

import { getUserApi } from '@/api/UserApi';
import { useAuth0 } from '@/contexts/Auth0Context';
import MetricCard from '@/metrics/components/MetricCard';
import type { GetViewerUserResponseBody, GetViewerCreditsResponseBody } from '@/api/UserApi';

export default function DebugUserPage() {
    return (
        <Wrapper>
            <Typography variant="h1">User Debug</Typography>
            <UserProfileSection />
            <PermissionsSection />
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

function decodeJwtPayload(token: string): Record<string, unknown> | null {
    const payloadPart = token.split('.')[1];
    if (!payloadPart) {
        return null;
    }
    const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
    return JSON.parse(atob(`${normalized}${padding}`)) as Record<string, unknown>;
}

function PermissionsSection() {
    const { isAuthenticated, getAccessToken } = useAuth0();
    const [permissions, setPermissions] = useState<string[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPermissions = async () => {
            if (!isAuthenticated) {
                setLoading(false);
                return;
            }

            setLoading(true);
            setError(null);

            try {
                // Permissions live in the access token's `permissions` claim, not in
                // /userinfo. Decode (not validate — the backend validates) to display them.
                const token = await getAccessToken();
                const payload = decodeJwtPayload(token);
                setPermissions(
                    Array.isArray(payload?.permissions) ? (payload.permissions as string[]) : []
                );
            } catch (err) {
                console.error('Error decoding permissions:', err);
                setError(err instanceof Error ? err.message : 'Failed to load permissions');
            } finally {
                setLoading(false);
            }
        };

        fetchPermissions();
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
                        Permissions
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
                        Permissions
                    </Typography>
                    <Alert severity="error">{error}</Alert>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'success.main' }}>
            <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <VpnKeyIcon sx={{ mr: 1, color: 'success.main' }} />
                    <Typography variant="h6">Permissions</Typography>
                </Box>

                {permissions && permissions.length > 0 ? (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {permissions.map((permission) => (
                            <Chip
                                key={permission}
                                label={permission}
                                size="small"
                                sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                            />
                        ))}
                    </Box>
                ) : (
                    <Alert severity="info">This user has no permissions in the access token.</Alert>
                )}
            </CardContent>
        </Card>
    );
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
