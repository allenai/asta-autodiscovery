'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Tab, Tabs, Typography, styled } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';

import { useAuth0 } from '@/contexts/Auth0Context';
import AuthButton from '@/components/AuthButton';
import { auth0Client } from '@/auth/Auth0Client';

const ADMIN_PERMISSION = 'enroll:autodiscovery_admin';

export default function MetricsLayout({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
    const router = useRouter();
    const pathname = usePathname();
    const [hasAdminPermission, setHasAdminPermission] = useState<boolean | null>(null);

    useEffect(() => {
        const checkAdminPermission = async () => {
            if (!isAuthenticated || !auth0Client) {
                setHasAdminPermission(false);
                return;
            }
            try {
                const token = await auth0Client.getTokenSilently();
                const parts = token.split('.');
                const payload = JSON.parse(atob(parts[1]));
                const permissions: string[] = payload.permissions || [];
                setHasAdminPermission(permissions.includes(ADMIN_PERMISSION));
            } catch {
                setHasAdminPermission(false);
            }
        };

        if (!isLoading) {
            checkAdminPermission();
        }
    }, [isAuthenticated, isLoading]);

    if (isLoading || hasAdminPermission === null) {
        return (
            <CenteredBox>
                <CircularProgress />
            </CenteredBox>
        );
    }

    if (!isAuthenticated) {
        return (
            <CenteredBox>
                <Typography variant="h6" sx={{ mb: 2, color: (theme: any) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)' }}>
                    Sign in to access the Metrics Dashboard
                </Typography>
                <AuthButton />
            </CenteredBox>
        );
    }

    if (!hasAdminPermission) {
        return (
            <CenteredBox>
                <Typography variant="h6" sx={{ mb: 1 }}>
                    Access Denied
                </Typography>
                <Typography variant="body2" sx={{ color: (theme: any) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)', mb: 2 }}>
                    The metrics dashboard requires the <code>{ADMIN_PERMISSION}</code> permission.
                </Typography>
                <AuthButton />
            </CenteredBox>
        );
    }

    const currentTab = pathname === '/metrics' || pathname === '/metrics/'
        ? 0
        : pathname.startsWith('/metrics/users')
            ? 1
            : pathname.startsWith('/metrics/runs')
                ? 2
                : 0;

    return (
        <Wrapper>
            <TopBar>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Title>Metrics Dashboard</Title>
                    <Tabs
                        value={currentTab}
                        onChange={(_, v) => {
                            if (v === 0) router.push('/metrics');
                            if (v === 1) router.push('/metrics/users');
                        }}
                        sx={{
                            minHeight: 36,
                            '& .MuiTab-root': {
                                minHeight: 36,
                                fontSize: '0.8rem',
                                textTransform: 'none',
                                color: 'rgba(255,255,255,0.6)',
                                '&.Mui-selected': { color: '#FAF2E9' },
                            },
                        }}>
                        <Tab label="Overview" />
                        <Tab label="Users" />
                    </Tabs>
                </Box>
                <AuthButton />
            </TopBar>
            <Content>{children}</Content>
        </Wrapper>
    );
}

const CenteredBox = styled(Box)`
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: ${({ theme }) => theme.spacing(4)};
`;

const Wrapper = styled(Box)`
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background: ${({ theme }) => theme.color['extra-dark-teal-100']?.hex || '#0f1a1a'};
`;

const TopBar = styled(Box)`
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: ${({ theme }) => theme.spacing(1.5, 3)};
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
`;

const Title = styled(Typography)`
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const Content = styled(Box)`
    flex: 1;
    overflow: auto;
    padding: ${({ theme }) => theme.spacing(3)};
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
`;
