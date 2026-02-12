'use client';

import { Box, Typography, styled } from '@mui/material';

const STATUS_COLORS: Record<string, string> = {
    SUCCEEDED: '#2dd4bf',
    FAILED: '#f87171',
    CANCELLED: '#fbbf24',
    RUNNING: '#818cf8',
    PENDING: '#a78bfa',
    CREATED: '#7a7f94',
    DELETED: '#525866',
};

interface StatusDistributionChartProps {
    runsByStatus: Record<string, number>;
}

export default function StatusDistributionChart({ runsByStatus }: StatusDistributionChartProps) {
    const entries = Object.entries(runsByStatus).sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...entries.map(([, v]) => v), 1);

    return (
        <ChartPanel>
            <PanelTitle>Runs by Status</PanelTitle>
            <BarChart>
                {entries.map(([status, count]) => {
                    const pct = (count / maxVal) * 100;
                    const color = STATUS_COLORS[status] || '#7a7f94';
                    return (
                        <BarRow key={status}>
                            <BarLabel>{status}</BarLabel>
                            <BarTrack>
                                <BarFill
                                    style={{
                                        width: `${Math.max(pct, 1.5)}%`,
                                        background: color,
                                    }}>
                                    <BarValue $outside={pct < 12}>{count.toLocaleString()}</BarValue>
                                </BarFill>
                            </BarTrack>
                        </BarRow>
                    );
                })}
            </BarChart>
        </ChartPanel>
    );
}

const ChartPanel = styled(Box)`
    background: ${({ theme }) => theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
    padding: ${({ theme }) => theme.spacing(3, 2.5)};
`;

const PanelTitle = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const BarChart = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: 10px;
`;

const BarRow = styled(Box)`
    display: grid;
    grid-template-columns: 100px 1fr;
    align-items: center;
    gap: 12px;
`;

const BarLabel = styled(Typography)`
    font-size: 0.75rem;
    text-align: right;
    font-weight: 500;
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const BarTrack = styled(Box)`
    position: relative;
    height: 28px;
    display: flex;
    align-items: center;
`;

const BarFill = styled(Box)`
    height: 100%;
    border-radius: 5px;
    display: flex;
    align-items: center;
    min-width: 2px;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    position: relative;
`;

const BarValue = styled('span')<{ $outside: boolean }>`
    font-size: 0.68rem;
    font-weight: 600;
    white-space: nowrap;
    padding: 0 8px;
    ${({ $outside }) =>
        $outside
            ? `
        position: absolute;
        left: calc(100% + 6px);
        color: rgba(255,255,255,0.8);
    `
            : `
        color: #fff;
    `}
`;
