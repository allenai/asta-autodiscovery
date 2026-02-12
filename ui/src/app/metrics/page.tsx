'use client';

import { useCallback, useEffect, useState } from 'react';
import { Box, CircularProgress, Typography, styled, Button } from '@mui/material';

import { getMetricsApi } from '@/api/MetricsApi';
import type { OverviewMetrics } from '@/types/Metrics';
import MetricCard from './components/MetricCard';
import TimePeriodFilter from './components/TimePeriodFilter';
import StatusDistributionChart from './components/StatusDistributionChart';
import CostBreakdownChart from './components/CostBreakdownChart';
import AggregatedUsageDialog from './components/AggregatedUsageDialog';

export default function MetricsOverviewPage() {
    const [data, setData] = useState<OverviewMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [usageDialogOpen, setUsageDialogOpen] = useState(false);

    const fetchData = useCallback(async (sd?: string, ed?: string) => {
        setLoading(true);
        setError(null);
        try {
            const api = getMetricsApi();
            const { data: overview } = await api.getOverview({
                startDate: sd || undefined,
                endDate: ed || undefined,
            });
            setData(overview);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load metrics');
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
    const handleRefreshCache = async () => {
        try {
            const api = getMetricsApi();
            await api.refreshCache();
            // Wait a moment for refresh to start, then re-fetch
            setTimeout(() => fetchData(startDate || undefined, endDate || undefined), 2000);
        } catch {
            // Ignore refresh errors
        }
    };

    if (loading && !data) {
        return (
            <CenteredBox>
                <CircularProgress />
                <Typography variant="body2" sx={{ mt: 2, color: (theme: any) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)' }}>
                    Loading metrics (first load may take a minute while scanning data)...
                </Typography>
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

    if (!data) return null;

    const fmtCost = (v: number) => `$${v.toFixed(2)}`;
    const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`;

    return (
        <Box>
            <TimePeriodFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={setStartDate}
                onEndDateChange={setEndDate}
                onApply={handleApplyFilter}
                onClear={handleClearFilter}
            />

            {/* Key Metric Cards */}
            <CardGrid>
                <MetricCard value={data.total_runs.toLocaleString()} label="Total Runs" />
                <MetricCard
                    value={fmtPct(data.success_rate)}
                    label="Success Rate"
                    subValue={`${data.succeeded_runs} succeeded / ${data.succeeded_runs + data.failed_runs} terminal`}
                />
                <MetricCard value={data.unique_users.toLocaleString()} label="Unique Users" />
                <MetricCard
                    value={data.total_experiments.toLocaleString()}
                    label="Experiments"
                    subValue={`${fmtPct(data.experiment_completion_rate)} completion rate`}
                />
                <MetricCard
                    value={fmtPct(data.share_rate)}
                    label="Share Rate"
                    subValue="Runs with sharing enabled"
                />
            </CardGrid>

            {/* LLM Usage */}
            <Subsection>
                <SubsectionHeader>
                    <SubsectionTitle>LLM Usage</SubsectionTitle>
                    <Button
                        size="small"
                        onClick={() => setUsageDialogOpen(true)}
                        sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                        Detailed Breakdown
                    </Button>
                </SubsectionHeader>
                <CardGrid>
                    <MetricCard
                        value={fmtCost(data.llm_cost_usd)}
                        label="Total LLM Cost"
                    />
                    <MetricCard
                        value={data.cost_per_hypothesis_usd != null ? fmtCost(data.cost_per_hypothesis_usd) : 'N/A'}
                        label="LLM Cost / Hypothesis"
                    />
                    <MetricCard
                        value={data.hypotheses_with_usage.toLocaleString()}
                        label="Hypotheses with Usage Data"
                        subValue={`of ${data.total_experiments.toLocaleString()} total`}
                    />
                </CardGrid>
            </Subsection>

            <AggregatedUsageDialog
                open={usageDialogOpen}
                onClose={() => setUsageDialogOpen(false)}
                startDate={startDate || undefined}
                endDate={endDate || undefined}
            />

            {/* Charts */}
            <ChartRow>
                <Box sx={{ flex: 1 }}>
                    <StatusDistributionChart runsByStatus={data.runs_by_status} />
                </Box>
                <Box sx={{ flex: 1.5 }}>
                    <CostBreakdownChart timeSeries={data.time_series} />
                </Box>
            </ChartRow>

            {/* Cache info */}
            <CacheInfo>
                {data.cache_refreshed_at && (
                    <Typography variant="caption" sx={{ color: (theme: any) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)' }}>
                        Data as of {new Date(data.cache_refreshed_at).toLocaleString()}
                    </Typography>
                )}
                <Button size="small" onClick={handleRefreshCache} sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                    Refresh Cache
                </Button>
            </CacheInfo>
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
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: ${({ theme }) => theme.spacing(1.5)};
    margin-bottom: ${({ theme }) => theme.spacing(2)};
`;

const ChartRow = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    margin-top: ${({ theme }) => theme.spacing(2)};

    @media (max-width: 768px) {
        flex-direction: column;
    }
`;

const Subsection = styled(Box)`
    margin-top: ${({ theme }: any) => theme.spacing(1)};
    margin-bottom: ${({ theme }: any) => theme.spacing(2)};
    padding: ${({ theme }: any) => theme.spacing(2, 2.5)};
    background: ${({ theme }: any) => theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid ${({ theme }: any) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
`;

const SubsectionHeader = styled(Box)`
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: ${({ theme }: any) => theme.spacing(1.5)};
`;

const SubsectionTitle = styled(Typography)`
    font-size: 0.8rem;
    font-weight: 600;
    color: ${({ theme }: any) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const CacheInfo = styled(Box)`
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing(2)};
    margin-top: ${({ theme }) => theme.spacing(3)};
    padding-top: ${({ theme }) => theme.spacing(2)};
    border-top: 1px solid ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
`;
