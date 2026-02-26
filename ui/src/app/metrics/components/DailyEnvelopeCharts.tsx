'use client';

import { useMemo, useState } from 'react';
import { Box, Button, Typography, styled } from '@mui/material';

import type { DailyMetrics } from '@/types/Metrics';

const MAX_DEFAULT_DAYS = 30;
const MAX_RANGE_DAYS = 3650;

type EnvelopeRow = {
    date: string;
    hypotheses_conducted: number;
    runs_started: number;
    unique_users_started: number;
};

type MetricKey = 'hypotheses_conducted' | 'runs_started' | 'unique_users_started';

type MetricDef = {
    key: MetricKey;
    title: string;
    color: string;
};

const METRICS: MetricDef[] = [
    {
        key: 'hypotheses_conducted',
        title: 'Hypotheses Conducted',
        color: '#f59e0b',
    },
    {
        key: 'runs_started',
        title: 'Runs Started',
        color: '#818cf8',
    },
    {
        key: 'unique_users_started',
        title: 'Unique Users that started runs',
        color: '#2dd4bf',
    },
];

interface DailyEnvelopeChartsProps {
    timeSeries: DailyMetrics[];
    startDate?: string;
    endDate?: string;
}

function parseDate(date: string): Date | null {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
    const parsed = new Date(`${date}T00:00:00Z`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function toDateString(date: Date): string {
    return date.toISOString().slice(0, 10);
}

function addDays(date: Date, days: number): Date {
    const next = new Date(date.getTime());
    next.setUTCDate(next.getUTCDate() + days);
    return next;
}

function clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(value, max));
}

function formatYAxisTick(value: number): string {
    if (value >= 1000) return Math.round(value).toLocaleString();
    if (value >= 10) return Math.round(value).toString();
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(1);
}

function buildDisplaySeries(
    timeSeries: DailyMetrics[],
    startDate?: string,
    endDate?: string
): EnvelopeRow[] {
    const dailyMap = new Map<string, EnvelopeRow>();
    for (const day of timeSeries) {
        dailyMap.set(day.date, {
            date: day.date,
            hypotheses_conducted: Number(day.hypotheses_conducted || 0),
            runs_started: Number(day.runs_started || 0),
            unique_users_started: Number(day.unique_users_started || 0),
        });
    }

    const sortedDates: string[] = [];
    dailyMap.forEach((_, key) => {
        sortedDates.push(key);
    });
    sortedDates.sort();
    const earliestDataDate = sortedDates[0] ? parseDate(sortedDates[0]) : null;
    const latestDataDate =
        sortedDates.length > 0 ? parseDate(sortedDates[sortedDates.length - 1]) : null;

    const startParsed = startDate ? parseDate(startDate) : null;
    const endParsed = endDate ? parseDate(endDate) : null;

    let rangeStart: Date | null = null;
    let rangeEnd: Date | null = null;

    if (startParsed && endParsed) {
        rangeStart = startParsed;
        rangeEnd = endParsed;
    } else if (startParsed) {
        rangeStart = startParsed;
        rangeEnd = latestDataDate || startParsed;
    } else if (endParsed) {
        rangeStart = earliestDataDate || endParsed;
        rangeEnd = endParsed;
    } else if (latestDataDate) {
        rangeEnd = latestDataDate;
        rangeStart = addDays(rangeEnd, -(MAX_DEFAULT_DAYS - 1));
    }

    if (!rangeStart || !rangeEnd) return [];

    if (rangeStart > rangeEnd) {
        const tmp = rangeStart;
        rangeStart = rangeEnd;
        rangeEnd = tmp;
    }

    const rows: EnvelopeRow[] = [];
    let cursor = rangeStart;
    for (let i = 0; i < MAX_RANGE_DAYS && cursor <= rangeEnd; i += 1) {
        const date = toDateString(cursor);
        rows.push(
            dailyMap.get(date) || {
                date,
                hypotheses_conducted: 0,
                runs_started: 0,
                unique_users_started: 0,
            }
        );
        cursor = addDays(cursor, 1);
    }

    return rows;
}

function exportRowsToCsv(rows: EnvelopeRow[]): void {
    const header = 'date,hypotheses_conducted,runs_started,unique_users_started';
    const lines = rows.map(
        (r) => `${r.date},${r.hypotheses_conducted},${r.runs_started},${r.unique_users_started}`
    );
    const csvText = [header, ...lines].join('\n');

    const start = rows[0]?.date || 'start';
    const end = rows[rows.length - 1]?.date || 'end';
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `daily-envelope-metrics_${start}_to_${end}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

export default function DailyEnvelopeCharts({
    timeSeries,
    startDate,
    endDate,
}: DailyEnvelopeChartsProps) {
    const rows = useMemo(
        () => buildDisplaySeries(timeSeries, startDate, endDate),
        [timeSeries, startDate, endDate]
    );

    return (
        <Section>
            <SectionHeader>
                <Box>
                    <SectionTitle>Daily Activity Metrics</SectionTitle>
                    <SectionSubtitle>
                        Daily hypotheses conducted, runs started, and unique users starting runs.
                    </SectionSubtitle>
                </Box>
                <Button
                    size="small"
                    disabled={rows.length === 0}
                    onClick={() => exportRowsToCsv(rows)}
                    sx={{ textTransform: 'none', fontSize: '0.72rem' }}>
                    Export CSV
                </Button>
            </SectionHeader>

            <ChartGrid>
                {METRICS.map((metric) => (
                    <MiniLineChartCard key={metric.key} rows={rows} metric={metric} />
                ))}
            </ChartGrid>
        </Section>
    );
}

function MiniLineChartCard({ rows, metric }: { rows: EnvelopeRow[]; metric: MetricDef }) {
    const [hoverIndex, setHoverIndex] = useState<number | null>(null);
    const [hoverX, setHoverX] = useState(0);
    const [plotWidth, setPlotWidth] = useState(0);

    if (rows.length === 0) {
        return (
            <Card>
                <CardTitle>{metric.title}</CardTitle>
                <NoDataText>No data for selected period.</NoDataText>
            </Card>
        );
    }

    const values = rows.map((r) => r[metric.key]);
    const maxValue = Math.max(...values, 1);
    const yTicks = [maxValue, maxValue / 2, 0];

    const toX = (index: number): number => {
        if (rows.length <= 1) return 50;
        return (index / (rows.length - 1)) * 100;
    };

    const toY = (value: number): number => 42 - (value / maxValue) * 42;

    const linePoints = rows.map((row, index) => `${toX(index)},${toY(row[metric.key])}`).join(' ');

    const areaPath = `M ${toX(0)} 42 L ${rows
        .map((row, index) => `${toX(index)} ${toY(row[metric.key])}`)
        .join(' L ')} L ${toX(rows.length - 1)} 42 Z`;

    const activeRow = hoverIndex != null ? rows[hoverIndex] : null;
    const activeValue = activeRow ? activeRow[metric.key] : 0;
    const activePointX = hoverIndex != null ? toX(hoverIndex) : 0;
    const activePointY = hoverIndex != null ? toY(activeValue) : 0;

    return (
        <Card>
            <CardTitle>{metric.title}</CardTitle>

            <PlotRow>
                <YAxis>
                    {yTicks.map((tick, idx) => (
                        <YTick key={idx}>{formatYAxisTick(tick)}</YTick>
                    ))}
                </YAxis>

                <Plot
                    onMouseMove={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        if (rect.width <= 0) return;
                        const x = clamp(e.clientX - rect.left, 0, rect.width);
                        const index =
                            rows.length <= 1 ? 0 : Math.round((x / rect.width) * (rows.length - 1));
                        setHoverIndex(clamp(index, 0, rows.length - 1));
                        setHoverX(x);
                        setPlotWidth(rect.width);
                    }}
                    onMouseLeave={() => setHoverIndex(null)}>
                    <Svg viewBox="0 0 100 42" preserveAspectRatio="none">
                        <GridLine x1="0" y1="42" x2="100" y2="42" />
                        <GridLine x1="0" y1="21" x2="100" y2="21" />
                        <GridLine x1="0" y1="0" x2="100" y2="0" />

                        <AreaPath d={areaPath} fill={metric.color} opacity={0.12} />
                        <Line points={linePoints} stroke={metric.color} />

                        {hoverIndex != null && (
                            <>
                                <HoverLine x1={activePointX} y1="0" x2={activePointX} y2="42" />
                                <HoverPoint
                                    cx={activePointX}
                                    cy={activePointY}
                                    r="1.3"
                                    fill={metric.color}
                                />
                            </>
                        )}
                    </Svg>

                    {activeRow && (
                        <Tooltip
                            style={{
                                left: `${clamp(hoverX, 76, Math.max(76, plotWidth - 76))}px`,
                            }}>
                            <TooltipDate>{activeRow.date}</TooltipDate>
                            <TooltipValue>{activeValue.toLocaleString()}</TooltipValue>
                        </Tooltip>
                    )}
                </Plot>
            </PlotRow>

            <DateRow>
                <DateLabel>{rows[0]?.date.slice(5) || '-'}</DateLabel>
                <DateLabel>{rows[rows.length - 1]?.date.slice(5) || '-'}</DateLabel>
            </DateRow>
        </Card>
    );
}

const Section = styled(Box)`
    margin-top: ${({ theme }) => theme.spacing(2.5)};
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    padding: ${({ theme }) => theme.spacing(2.5)};
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
`;

const SectionHeader = styled(Box)`
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: ${({ theme }) => theme.spacing(1.5)};
    margin-bottom: ${({ theme }) => theme.spacing(2)};
`;

const SectionTitle = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const SectionSubtitle = styled(Typography)`
    margin-top: 2px;
    font-size: 0.7rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const ChartGrid = styled(Box)`
    display: grid;
    gap: ${({ theme }) => theme.spacing(1.5)};
    grid-template-columns: repeat(3, minmax(0, 1fr));

    @media (max-width: 900px) {
        grid-template-columns: 1fr;
    }
`;

const Card = styled(Box)`
    padding: ${({ theme }) => theme.spacing(1.5)};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 12px;
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.02)'};
    min-width: 0;
`;

const CardTitle = styled(Typography)`
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const Plot = styled(Box)`
    position: relative;
    height: 132px;
    flex: 1;
    min-width: 0;
`;

const PlotRow = styled(Box)`
    display: flex;
    gap: 8px;
    align-items: stretch;
`;

const YAxis = styled(Box)`
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: flex-end;
    width: 36px;
    padding: 2px 0;
    flex-shrink: 0;
`;

const YTick = styled(Typography)`
    font-size: 0.58rem;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
`;

const Svg = styled('svg')`
    width: 100%;
    height: 100%;
    overflow: visible;
`;

const GridLine = styled('line')`
    stroke: rgba(255, 255, 255, 0.08);
    stroke-width: 0.3;
`;

const AreaPath = styled('path')``;

const Line = styled('polyline')`
    fill: none;
    stroke-width: 1.2;
    stroke-linejoin: round;
    stroke-linecap: round;
`;

const HoverLine = styled('line')`
    stroke: rgba(255, 255, 255, 0.45);
    stroke-width: 0.35;
    stroke-dasharray: 1.5 1.5;
`;

const HoverPoint = styled('circle')`
    stroke: #ffffff;
    stroke-width: 0.7;
`;

const Tooltip = styled(Box)`
    position: absolute;
    top: 4px;
    transform: translateX(-50%);
    z-index: 5;
    pointer-events: none;
    background: rgba(20, 24, 32, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 6px 10px;
    text-align: center;
    min-width: 106px;
`;

const TooltipDate = styled(Typography)`
    font-size: 0.62rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const TooltipValue = styled(Typography)`
    font-size: 0.76rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const DateRow = styled(Box)`
    margin-top: ${({ theme }) => theme.spacing(1)};
    display: flex;
    align-items: center;
    justify-content: space-between;
`;

const DateLabel = styled(Typography)`
    font-size: 0.6rem;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
`;

const NoDataText = styled(Typography)`
    margin-top: ${({ theme }) => theme.spacing(1)};
    font-size: 0.75rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;
