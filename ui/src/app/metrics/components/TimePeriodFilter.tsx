'use client';

import { Box, TextField, styled, Button } from '@mui/material';

interface TimePeriodFilterProps {
    startDate: string;
    endDate: string;
    onStartDateChange: (date: string) => void;
    onEndDateChange: (date: string) => void;
    onApply: () => void;
    onClear: () => void;
}

export default function TimePeriodFilter({
    startDate,
    endDate,
    onStartDateChange,
    onEndDateChange,
    onApply,
    onClear,
}: TimePeriodFilterProps) {
    return (
        <FilterRow>
            <StyledInput
                type="date"
                label="Start Date"
                value={startDate}
                onChange={(e) => onStartDateChange(e.target.value)}
                InputLabelProps={{ shrink: true }}
                size="small"
            />
            <StyledInput
                type="date"
                label="End Date"
                value={endDate}
                onChange={(e) => onEndDateChange(e.target.value)}
                InputLabelProps={{ shrink: true }}
                size="small"
            />
            <Button
                variant="outlined"
                size="small"
                onClick={onApply}
                sx={{
                    textTransform: 'none',
                    color: (theme: any) => theme.color['cream-100']?.hex || '#fff',
                    borderColor: 'rgba(255,255,255,0.2)',
                    '&:hover': { borderColor: 'rgba(255,255,255,0.4)' },
                }}>
                Apply
            </Button>
            {(startDate || endDate) && (
                <Button
                    size="small"
                    onClick={onClear}
                    sx={{
                        textTransform: 'none',
                        color: (theme: any) =>
                            theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)',
                    }}>
                    Clear
                </Button>
            )}
        </FilterRow>
    );
}

const FilterRow = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(1.5)};
    align-items: center;
    margin-bottom: ${({ theme }) => theme.spacing(3)};
    flex-wrap: wrap;
`;

const StyledInput = styled(TextField)`
    & .MuiInputBase-root {
        font-size: 0.8rem;
        color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
        background: ${({ theme }) =>
            theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
        border-radius: 8px;
    }
    & .MuiInputBase-root fieldset {
        border-color: ${({ theme }) =>
            theme.color['cream-20']?.rgba?.toString() || 'rgba(255,255,255,0.2)'};
    }
    & .MuiInputBase-root:hover fieldset {
        border-color: ${({ theme }) =>
            theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    }
    & .MuiInputLabel-root {
        font-size: 0.8rem;
        color: ${({ theme }) =>
            theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    }
    & .MuiSvgIcon-root {
        color: ${({ theme }) =>
            theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    }
    width: 160px;
`;
