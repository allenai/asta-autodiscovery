'use client';

import { Box, Button, styled } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useRouter } from 'next/navigation';

import AuthButton from '@/components/AuthButton';
import CreditsChip from '@/components/CreditsChip';
import { AboutButton } from '@/components/AboutButton';
import { FeedbackButton } from '@/components/FeedbackButton';
import { useAuth0 } from '@/contexts/Auth0Context';

interface HeaderProps {
    showBackButton?: boolean;
}

export default function Header({ showBackButton = false }: HeaderProps) {
    const { isAuthenticated } = useAuth0();
    const router = useRouter();

    const handleBack = () => {
        router.back();
    };

    return (
        <StyledHeader>
            {showBackButton && (
                <BackButton onClick={handleBack} variant="outlined" startIcon={<ArrowBackIcon />}>
                    Back
                </BackButton>
            )}
            {isAuthenticated && (
                <LeftAlignedCredits>
                    <CreditsChip />
                </LeftAlignedCredits>
            )}
            <DesktopFeedback>
                <FeedbackButton />
            </DesktopFeedback>
            <AboutButton />
            <AuthButton />
        </StyledHeader>
    );
}

const LeftAlignedCredits = styled('div')`
    @media (max-width: 600px) {
        margin-right: auto;
    }
`;

const DesktopFeedback = styled('div')`
    @media (max-width: 600px) {
        display: none;
    }
`;

const StyledHeader = styled(Box)`
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: ${({ theme }) => theme.spacing(2)};
    padding: ${({ theme }) => theme.spacing(2)};

    @media (max-width: 600px) {
        flex-wrap: nowrap;
        padding-top: 0;
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
        border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }
`;

const BackButton = styled(Button)`
    margin-right: auto;

    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;
        white-space: nowrap;

        & .MuiButton-startIcon {
            margin: 0 ${({ theme }) => theme.spacing(0.75)} 0 0;
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};

        &:hover {
            border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        }
    }
`;
