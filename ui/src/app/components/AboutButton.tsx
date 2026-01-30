import { Button, styled } from '@mui/material';
import Link from 'next/link';

export const AboutButton = () => {
    return (
        <Link
            href="https://arxiv.org/pdf/2507.00310"
            passHref
            target="_blank"
            rel="noopener noreferrer">
            <StyledButton variant="outlined">About AutoDiscovery</StyledButton>
        </Link>
    );
};

const StyledButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;

        & .MuiButton-endIcon {
            margin: 0 0 0 ${({ theme }) => theme.spacing(0.75)};
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};

        &:hover {
            border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        }
    }
`;
