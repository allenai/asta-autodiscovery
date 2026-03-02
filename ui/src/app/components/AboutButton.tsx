import { Button, styled } from '@mui/material';
import Link from 'next/link';

import { TEST_ID_ABOUT_BUTTON } from '@/testIds';

export const AboutButton = () => {
    return (
        <Link
            href="https://allenai.org/blog/autodiscovery"
            passHref
            target="_blank"
            rel="noopener noreferrer"
            data-test-id={TEST_ID_ABOUT_BUTTON}>
            <StyledButton variant="outlined">
                About<DesktopOnly>&nbsp;AutoDiscovery</DesktopOnly>
            </StyledButton>
        </Link>
    );
};

const DesktopOnly = styled('span')`
    @media (max-width: 600px) {
        display: none;
    }
`;

const StyledButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;
        white-space: nowrap;

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
