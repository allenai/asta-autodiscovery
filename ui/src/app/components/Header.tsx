'use client';

import { Box, Button, styled } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useRouter, usePathname } from 'next/navigation';

import AuthButton from '@/components/AuthButton';
import CreditsChip from '@/components/CreditsChip';
import { AboutButton } from '@/components/AboutButton';
import { FeedbackButton } from '@/components/FeedbackButton';
import { useAuth0 } from '@/contexts/Auth0Context';
import { filterTransientProps } from '@/utils/styledProps';

// Smart component — reads hooks, computes props, delegates rendering
export function Header() {
    const { isAuthenticated } = useAuth0();
    const router = useRouter();
    const pathname = usePathname();

    return (
        <HeaderView
            showBackButton={pathname.includes('/shared') && !isAuthenticated}
            showCredits={isAuthenticated}
            isSharedSamples={pathname.startsWith('/shared/samples')}
            onBack={() => router.push('/runs')}
        />
    );
}

// Dumb component — no hooks, accepts all variable data as explicit props
interface HeaderViewProps {
    showBackButton: boolean;
    showCredits: boolean;
    isSharedSamples: boolean;
    onBack: () => void;
}

export function HeaderView({
    showBackButton,
    showCredits,
    isSharedSamples,
    onBack,
}: HeaderViewProps) {
    return (
        <StyledHeader $isSharedSamples={isSharedSamples}>
            {showBackButton && (
                <BackButton onClick={onBack} variant="outlined" startIcon={<ArrowBackIcon />}>
                    Back
                </BackButton>
            )}
            {showCredits && (
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

const StyledHeader = styled(Box, { shouldForwardProp: filterTransientProps })<{
    $isSharedSamples: boolean;
}>`
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: ${({ theme }) => theme.spacing(2)};
    padding: ${({ theme }) => theme.spacing(2)};
    padding-top: ${({ theme, $isSharedSamples }) =>
        $isSharedSamples ? theme.spacing(3) : theme.spacing(2)};

    @media (max-width: 600px) {
        flex-wrap: nowrap;
        padding-top: ${({ theme, $isSharedSamples }) =>
            $isSharedSamples ? theme.spacing(2) : '0'};
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
