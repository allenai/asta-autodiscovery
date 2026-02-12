'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Typography, styled, Button, Chip } from '@mui/material';
import { useParams, useRouter } from 'next/navigation';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { getMetricsApi } from '@/api/MetricsApi';
import type { RunMetrics } from '@/types/Metrics';
import MetricCard from '../../../components/MetricCard';
import LLMUsageDashboard from '../../../components/LLMUsageDashboard';

const STATUS_COLORS: Record<string, string> = {
    SUCCEEDED: 'success',
    FAILED: 'error',
    CANCELLED: 'warning',
    RUNNING: 'info',
    PENDING: 'info',
    CREATED: 'default',
    DELETED: 'default',
};

export default function RunMetricsPage() {
    const params = useParams();
    const router = useRouter();
    const userid = decodeURIComponent(params.userid as string);
    const runid = decodeURIComponent(params.runid as string);

    const [data, setData] = useState<RunMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const api = getMetricsApi();
                const { data: metrics } = await api.getRunMetrics(userid, runid);
                setData(metrics);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load run metrics');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [userid, runid]);

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
                <Typography color="error">{error || 'Run not found'}</Typography>
            </CenteredBox>
        );
    }

    const fmtCost = (v: number) => `$${v.toFixed(2)}`;
    const fmtDuration = (secs: number | null) => {
        if (secs == null) return '-';
        if (secs < 60) return `${secs.toFixed(0)}s`;
        if (secs < 3600) return `${(secs / 60).toFixed(1)}m`;
        return `${(secs / 3600).toFixed(1)}h`;
    };

    return (
        <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Button
                    size="small"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => router.push(`/metrics/users/${encodeURIComponent(userid)}`)}
                    sx={{ textTransform: 'none' }}>
                    {userid.length > 30 ? userid.slice(0, 30) + '...' : userid}
                </Button>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {data.name || data.runid}
                </Typography>
                <Chip
                    label={data.status}
                    size="small"
                    color={(STATUS_COLORS[data.status] as any) || 'default'}
                    sx={{ fontSize: '0.7rem', height: 24 }}
                />
                {data.is_shared && (
                    <Chip
                        label="Shared"
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.65rem', height: 22 }}
                    />
                )}
            </Box>

            <InfoRow>
                {data.model && <InfoItem>Model: {data.model}</InfoItem>}
                {data.domain && <InfoItem>Domain: {data.domain}</InfoItem>}
                {data.created_at && (
                    <InfoItem>Created: {new Date(data.created_at).toLocaleString()}</InfoItem>
                )}
                {data.duration_seconds != null && (
                    <InfoItem>Duration: {fmtDuration(data.duration_seconds)}</InfoItem>
                )}
            </InfoRow>

            {/* Cost & Experiment Cards */}
            <CardGrid>
                <MetricCard value={fmtCost(data.llm_cost_usd)} label="LLM Cost" />
                <MetricCard
                    value={`${data.n_experiments_completed}/${data.n_experiments_requested}`}
                    label="Experiments"
                />
            </CardGrid>

            {/* LLM Cost by Model */}
            {data.llm_cost_by_model && Object.keys(data.llm_cost_by_model).length > 0 && (
                <Panel>
                    <PanelTitle>Cost by Model</PanelTitle>
                    <CostList>
                        {Object.entries(data.llm_cost_by_model)
                            .sort((a, b) => b[1] - a[1])
                            .map(([model, cost]) => (
                                <CostRow key={model}>
                                    <CostModel>{model}</CostModel>
                                    <CostValue>{fmtCost(cost)}</CostValue>
                                </CostRow>
                            ))}
                    </CostList>
                </Panel>
            )}

            {/* Full LLM Usage Dashboard */}
            {data.llm_usage_summary && (
                <Box sx={{ mt: 3 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                        LLM Usage Details
                    </Typography>
                    <LLMUsageDashboard
                        usage={data.llm_usage_summary}
                        costByModel={data.llm_cost_by_model}
                    />
                </Box>
            )}

            {!data.llm_usage_summary && (
                <Panel sx={{ mt: 3 }}>
                    <Typography
                        variant="body2"
                        sx={{
                            color: (theme: any) =>
                                theme.color['cream-60']?.rgba?.toString() ||
                                'rgba(255,255,255,0.6)',
                        }}>
                        LLM usage data is not available for this run.
                    </Typography>
                </Panel>
            )}
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

const InfoRow = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    flex-wrap: wrap;
    margin-bottom: ${({ theme }) => theme.spacing(2.5)};
`;

const InfoItem = styled(Typography)`
    font-size: 0.78rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const CardGrid = styled(Box)`
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: ${({ theme }) => theme.spacing(1.5)};
`;

const Panel = styled(Box)`
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
    padding: ${({ theme }) => theme.spacing(3, 2.5)};
    margin-top: ${({ theme }) => theme.spacing(2)};
`;

const PanelTitle = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: ${({ theme }) => theme.spacing(1.5)};
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const CostList = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: 6px;
`;

const CostRow = styled(Box)`
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
`;

const CostModel = styled(Typography)`
    font-size: 0.78rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const CostValue = styled(Typography)`
    font-size: 0.82rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
`;
