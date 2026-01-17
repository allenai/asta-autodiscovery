'use client';

import { useEffect, useRef, useState } from 'react';
import { Chip, Popover, styled } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';
import { getViewerCredits, ViewerCredits } from '@/user/actions';

export default function CreditsChip() {
    const [credits, setCredits] = useState<ViewerCredits | null>(null);
    const [lastError, setLastError] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(false);

    const anchorRef = useRef<HTMLDivElement | null>(null);

    const { isAuthenticated, getAccessToken } = useAuth0();
    useEffect(() => {
        if (!isAuthenticated) {
            return;
        }
        setLastError(null);
        getAccessToken()
            .then((token) => getViewerCredits({ token }))
            .then((credits) => setCredits(credits))
            .catch((error) => setLastError(error.message));
    }, [isAuthenticated]);

    return (
        <>
            <StyledChip
                ref={anchorRef}
                label={
                    <span>
                        Experiment Credits:{' '}
                        {lastError ? (
                            <ErrorText>Error</ErrorText>
                        ) : credits !== null ? (
                            credits.remaining.toLocaleString()
                        ) : (
                            <LoadingShimmer />
                        )}
                    </span>
                }
                onClick={() => setIsOpen(!isOpen)}
            />
            <Popover
                open={isOpen}
                onClose={() => setIsOpen(false)}
                anchorEl={anchorRef.current}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}>
                <PopoverContent>
                    {credits ? (
                        <>
                            <GridContainer>
                                <CreditValue>{credits.granted.toLocaleString()}</CreditValue>
                                <CreditLabel>Granted</CreditLabel>
                                <CreditValue>{credits.used.toLocaleString()}</CreditValue>
                                <CreditLabel>Used</CreditLabel>
                                <CreditValue>{credits.pending.toLocaleString()}</CreditValue>
                                <CreditLabel>Pending</CreditLabel>
                            </GridContainer>
                        </>
                    ) : lastError ? (
                        <pre>{lastError}</pre>
                    ) : (
                        <LoadingShimmer />
                    )}
                </PopoverContent>
            </Popover>
        </>
    );
}

const StyledChip = styled(Chip)`
    &.MuiChip-root {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
        border-radius: 4px;
        color: ${({ theme }) => theme.color['cream-100'].hex};
        font-size: 0.85rem;
        padding: ${({ theme }) => theme.spacing(0.5, 1)};
    }
`;

const ErrorText = styled('span')`
    color: ${({ theme }) => theme.color['error-red-80'].hex};
    margin-left: ${({ theme }) => theme.spacing(0.5)};
`;

const LoadingShimmer = styled('span')`
    display: inline-block;
    width: 2em;
    height: 1.2em;
    vertical-align: middle;
    margin-left: ${({ theme }) => theme.spacing(0.5)};
    background: linear-gradient(
        90deg,
        ${({ theme }) => theme.color['dark-teal-100'].hex} 25%,
        ${({ theme }) => theme.color['extra-dark-teal-100'].hex} 25%,
        ${({ theme }) => theme.color['dark-teal-100'].hex} 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;

    @keyframes shimmer {
        0% {
            background-position: 100% 0;
        }
        100% {
            background-position: -100% 0;
        }
    }
`;

const PopoverContent = styled('div')`
    padding: ${({ theme }) => theme.spacing(1)};
`;

const GridContainer = styled('div')`
    display: grid;
    grid-template-columns: auto auto;
    grid-template-rows: auto auto auto;
    gap: ${({ theme }) => theme.spacing(0.5, 1)};
    align-items: center;
`;

const CreditValue = styled('div')`
    font-weight: 600;
    justify-self: end;
`;

const CreditLabel = styled('div')`
    opacity: 0.8;
    font-size: 0.9em;
`;
