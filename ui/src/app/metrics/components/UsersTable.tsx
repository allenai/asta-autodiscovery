'use client';

import { useState } from 'react';
import { Box, Typography, styled } from '@mui/material';
import { useRouter } from 'next/navigation';

import type { UserMetricsSummary } from '@/types/Metrics';
import { scrollbarStyles } from '@/utils/scrollbar';

type SortKey = keyof UserMetricsSummary;

interface UsersTableProps {
    users: UserMetricsSummary[];
}

export default function UsersTable({ users }: UsersTableProps) {
    const router = useRouter();
    const [sortKey, setSortKey] = useState<SortKey>('llm_cost_usd');
    const [sortAsc, setSortAsc] = useState(false);

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortAsc(!sortAsc);
        } else {
            setSortKey(key);
            setSortAsc(false);
        }
    };

    const sorted = [...users].sort((a, b) => {
        const av = a[sortKey] ?? '';
        const bv = b[sortKey] ?? '';
        if (av < bv) return sortAsc ? -1 : 1;
        if (av > bv) return sortAsc ? 1 : -1;
        return 0;
    });

    const columns: { key: SortKey; label: string; format?: (v: any) => string; align?: string }[] =
        [
            {
                key: 'userid',
                label: 'User',
                align: 'left',
                format: (v: string) => (v.length > 24 ? v.slice(0, 24) + '...' : v),
            },
            { key: 'total_runs', label: 'Runs' },
            { key: 'succeeded_runs', label: 'Succeeded' },
            {
                key: 'success_rate',
                label: 'Success %',
                format: (v: number) => `${(v * 100).toFixed(1)}%`,
            },
            { key: 'total_experiments', label: 'Experiments' },
            { key: 'llm_cost_usd', label: 'LLM Cost', format: (v: number) => `$${v.toFixed(2)}` },
            { key: 'shared_runs', label: 'Shared' },
            {
                key: 'last_activity',
                label: 'Last Active',
                format: (v: string | null) => (v ? v.slice(0, 10) : '-'),
            },
        ];

    return (
        <TableWrapper>
            <StyledTable>
                <thead>
                    <tr>
                        {columns.map((col) => (
                            <Th
                                key={col.key}
                                $align={col.align || 'right'}
                                onClick={() => handleSort(col.key)}
                                style={{ cursor: 'pointer' }}>
                                {col.label}
                                {sortKey === col.key && (sortAsc ? ' \u25B2' : ' \u25BC')}
                            </Th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((user) => (
                        <ClickableRow
                            key={user.userid}
                            onClick={() =>
                                router.push(`/metrics/users/${encodeURIComponent(user.userid)}`)
                            }>
                            {columns.map((col) => {
                                const raw = user[col.key];
                                const formatted = col.format ? col.format(raw) : String(raw ?? '-');
                                return (
                                    <Td key={col.key} $align={col.align || 'right'}>
                                        {formatted}
                                    </Td>
                                );
                            })}
                        </ClickableRow>
                    ))}
                    {sorted.length === 0 && (
                        <tr>
                            <Td $align="center" colSpan={columns.length}>
                                <Typography
                                    variant="body2"
                                    sx={{
                                        py: 4,
                                        color: (theme: any) =>
                                            theme.color['cream-60']?.rgba?.toString() ||
                                            'rgba(255,255,255,0.6)',
                                    }}>
                                    No users found for the selected period.
                                </Typography>
                            </Td>
                        </tr>
                    )}
                </tbody>
            </StyledTable>
        </TableWrapper>
    );
}

const TableWrapper = styled(Box)`
    overflow-x: auto;
    ${({ theme }) => scrollbarStyles(theme)}
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
    user-select: none;

    &:hover {
        color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
    }
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
