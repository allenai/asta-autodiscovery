'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Typography, styled, Button, Chip } from '@mui/material';
import { useParams, useRouter } from 'next/navigation';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { getMetricsApi } from '@/api/MetricsApi';
import type { UserDetailMetrics } from '@/types/Metrics';
import MetricCard from '../../components/MetricCard';

const STATUS_COLORS: Record<string, string> = {
    SUCCEEDED: 'success',
    FAILED: 'error',
    CANCELLED: 'warning',
    RUNNING: 'info',
    PENDING: 'info',
    CREATED: 'default',
    DELETED: 'default',
};

export default function UserDetailPage() {
    const params = useParams();
    const router = useRouter();
    const userid = decodeURIComponent(params.userid as string);

    const [data, setData] = useState<UserDetailMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const api = getMetricsApi();
                const { data: detail } = await api.getUserDetail(userid);
                setData(detail);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load user detail');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [userid]);

    if (loading) {
        return (
            <CenteredBox>
                <CircularProgress />
            </CenteredBox>
        );
    }

    if (error || !data) {
        return (
            <CenteredBox>
                <Typography color="error">{error || 'User not found'}</Typography>
            </CenteredBox>
        );
    }

    const s = data.summary;
    const fmtCost = (v: number) => `$${v.toFixed(2)}`;
    const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`;
    const fmtDuration = (secs: number | null) => {
        if (secs == null) return '-';
        if (secs < 60) return `${secs.toFixed(0)}s`;
        return `${(secs / 60).toFixed(1)}m`;
    };

    return (
        <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Button
                    size="small"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => router.push('/metrics/users')}
                    sx={{ textTransform: 'none' }}>
                    Users
                </Button>
            </Box>

            <Typography variant="h6" sx={{ mb: 0.5, fontWeight: 600 }}>
                {userid}
            </Typography>
            {s.last_activity && (
                <Typography
                    variant="caption"
                    sx={{
                        color: (theme: any) =>
                            theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)',
                        mb: 2,
                        display: 'block',
                    }}>
                    Last active: {new Date(s.last_activity).toLocaleDateString()}
                </Typography>
            )}

            <CardGrid>
                <MetricCard value={s.total_runs.toLocaleString()} label="Total Runs" />
                <MetricCard value={fmtPct(s.success_rate)} label="Success Rate" />
                <MetricCard value={s.total_experiments.toLocaleString()} label="Experiments" />
                <MetricCard value={fmtCost(s.llm_cost_usd)} label="LLM Cost" />
                <MetricCard value={s.shared_runs.toLocaleString()} label="Shared Runs" />
            </CardGrid>

            {/* Runs table */}
            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1.5, fontWeight: 600 }}>
                Runs ({data.runs.length})
            </Typography>
            <TableWrapper>
                <StyledTable>
                    <thead>
                        <tr>
                            <Th $align="left">Run</Th>
                            <Th>Status</Th>
                            <Th>Model</Th>
                            <Th>Experiments</Th>
                            <Th>Duration</Th>
                            <Th>LLM Cost</Th>
                            <Th>Created</Th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.runs.map((run) => (
                            <ClickableRow
                                key={run.runid}
                                onClick={() =>
                                    router.push(
                                        `/metrics/runs/${encodeURIComponent(run.userid)}/${encodeURIComponent(run.runid)}`
                                    )
                                }>
                                <Td $align="left">{run.name || run.runid.slice(0, 8)}</Td>
                                <Td>
                                    <Chip
                                        label={run.status}
                                        size="small"
                                        color={(STATUS_COLORS[run.status] as any) || 'default'}
                                        sx={{ fontSize: '0.65rem', height: 22 }}
                                    />
                                </Td>
                                <Td>{run.model || '-'}</Td>
                                <Td>
                                    {run.n_experiments_completed}/{run.n_experiments_requested}
                                </Td>
                                <Td>{fmtDuration(run.duration_seconds)}</Td>
                                <Td>{fmtCost(run.llm_cost_usd)}</Td>
                                <Td>
                                    {run.created_at
                                        ? new Date(run.created_at).toLocaleDateString()
                                        : '-'}
                                </Td>
                            </ClickableRow>
                        ))}
                    </tbody>
                </StyledTable>
            </TableWrapper>
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

const CardGrid = styled(Box)`
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: ${({ theme }) => theme.spacing(1.5)};
    margin-top: ${({ theme }) => theme.spacing(2)};
`;

const TableWrapper = styled(Box)`
    overflow-x: auto;
`;

const StyledTable = styled('table')`
    width: 100%;
    border-collapse: collapse;
`;

const Th = styled('th')<{ $align?: string }>`
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
    text-align: ${({ $align }) => $align || 'right'};
    padding: 8px 10px;
    border-bottom: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    white-space: nowrap;
`;

const Td = styled('td')<{ $align?: string }>`
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
    text-align: ${({ $align }) => $align || 'right'};
    padding: 10px;
    border-bottom: 1px solid
        ${({ theme }) => theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const ClickableRow = styled('tr')`
    cursor: pointer;
    transition: background 0.15s;
    &:hover {
        background: ${({ theme }) =>
            theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    }
`;
