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
            <LeftSection>
                {showBackButton && (
                    <BackButton
                        onClick={handleBack}
                        variant="outlined"
                        startIcon={<ArrowBackIcon />}>
                        Back
                    </BackButton>
                )}
            </LeftSection>
            <RightSection>
                {isAuthenticated && <CreditsChip />}
                <FeedbackButton />
                <AboutButton />
                <AuthButton />
            </RightSection>
        </StyledHeader>
    );
}

const StyledHeader = styled(Box)`
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: ${({ theme }) => theme.spacing(2)};
`;

const LeftSection = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
`;

const RightSection = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
`;

const BackButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;

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
