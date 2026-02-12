'use client';

import { Box, Typography, styled } from '@mui/material';

interface MetricCardProps {
    value: string | number;
    label: string;
    subValue?: string;
}

export default function MetricCard({ value, label, subValue }: MetricCardProps) {
    return (
        <Card>
            <Value>{value}</Value>
            <Label>{label}</Label>
            {subValue && <SubValue>{subValue}</SubValue>}
        </Card>
    );
}

const Card = styled(Box)`
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 12px;
    padding: ${({ theme }) => theme.spacing(2.5, 2)};
    text-align: center;
`;

const Value = styled(Typography)`
    font-size: 1.5rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const Label = styled(Typography)`
    font-size: 0.7rem;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: ${({ theme }) => theme.spacing(0.5)};
`;

const SubValue = styled(Typography)`
    font-size: 0.72rem;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    margin-top: ${({ theme }) => theme.spacing(0.25)};
`;
