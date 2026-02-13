import { Chip, styled } from '@mui/material';
import { filterTransientProps } from '@/utils/styledProps';

export const StatusChip = styled(Chip, {
    shouldForwardProp: filterTransientProps,
})<{ $status: string }>`
    background-color: ${({ theme, $status }) => {
        const status = $status.toUpperCase();
        switch (status) {
            case 'FAILED':
            case 'ERROR':
                return theme.color['error-red-100'].hex;
            case 'CANCELLED':
                return theme.color['warning-orange-100'].hex;
            default:
                return theme.color['extra-dark-teal-100'].hex;
        }
    }};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    font-weight: normal;
    padding: ${({ theme }) => theme.spacing(1)};
`;
