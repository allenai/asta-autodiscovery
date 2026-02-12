'use client';

import { useCallback, useEffect, useState } from 'react';
import { Box, CircularProgress, Typography, styled, Button } from '@mui/material';

import { getMetricsApi } from '@/api/MetricsApi';
import type { UserMetricsSummary } from '@/types/Metrics';
import TimePeriodFilter from '../components/TimePeriodFilter';
import UsersTable from '../components/UsersTable';

export default function MetricsUsersPage() {
    const [users, setUsers] = useState<UserMetricsSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    const fetchData = useCallback(async (sd?: string, ed?: string) => {
        setLoading(true);
        setError(null);
        try {
            const api = getMetricsApi();
            const { data } = await api.getUsers({
                startDate: sd || undefined,
                endDate: ed || undefined,
            });
            setUsers(data.users);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load users');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleApplyFilter = () => fetchData(startDate, endDate);
    const handleClearFilter = () => {
        setStartDate('');
        setEndDate('');
        fetchData();
    };

    if (loading && users.length === 0) {
        return (
            <CenteredBox>
                <CircularProgress />
            </CenteredBox>
        );
    }

    if (error) {
        return (
            <CenteredBox>
                <Typography color="error">{error}</Typography>
                <Button onClick={() => fetchData()} sx={{ mt: 2, textTransform: 'none' }}>
                    Retry
                </Button>
            </CenteredBox>
        );
    }

    return (
        <Box>
            <Typography
                variant="h6"
                sx={{
                    mb: 2,
                    fontWeight: 600,
                    color: (theme: any) => theme.color['cream-100']?.hex || '#fff',
                }}>
                Users ({users.length})
            </Typography>

            <TimePeriodFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={setStartDate}
                onEndDateChange={setEndDate}
                onApply={handleApplyFilter}
                onClear={handleClearFilter}
            />

            <UsersTable users={users} />
        </Box>
    );
}

const CenteredBox = styled(Box)`
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: ${({ theme }) => theme.spacing(8)};
`;
