'use client';

import { useRef, useState } from 'react';
import { Chip, Popover, styled } from '@mui/material';
import Link from 'next/link';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';

export default function CreditsChip() {
    const { credits, lastError } = useViewerCredits();
    const [isOpen, setIsOpen] = useState(false);

    const anchorRef = useRef<HTMLDivElement | null>(null);

    return (
        <>
            <StyledChip
                ref={anchorRef}
                label={
                    <span>
                        Your Experiment Credits:{' '}
                        {lastError ? (
                            <ErrorText>Error</ErrorText>
                        ) : credits !== null ? (
                            <CreditsValue>{credits?.remaining.toLocaleString()}</CreditsValue>
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
                    <PopoverHeading>How experiment credits work</PopoverHeading>
                    <PopoverParagraph>
                        To support your research, we are providing a one-time grant of 1,000
                        credits.
                    </PopoverParagraph>
                    <ul>
                        <li>
                            <b>Exchange Rate:</b> 1 Credit = 1 Experiment.
                        </li>
                        <li>
                            <b>Budget Protection:</b> Discovery sessions are capped at 500 credits
                            to prevent accidental overspending. We recommend 50-100 experiments per
                            session.
                        </li>
                        <li>
                            <b>Expiration:</b> Credits are valid until Feb 28, 2026.
                        </li>
                    </ul>

                    <PopoverSubheading>Can I get more credits?</PopoverSubheading>
                    <PopoverParagraph>
                        This grant is a fixed allocation and credits cannot be reloaded once
                        consumed. However, we are actively evaluating future funding or premium
                        models. If you are interested in discussing potential partnerships, please{' '}
                        <StyledLink
                            href="https://allenai.org/contact"
                            target="_blank"
                            rel="noopener noreferrer">
                            contact us
                        </StyledLink>
                        .
                    </PopoverParagraph>

                    {credits !== null ? (
                        <CreditsReport>
                            <CreditLabel>Credits Used:</CreditLabel>
                            <CreditValue>{credits.used.toLocaleString()}</CreditValue>

                            <CreditLabel>Credits Pending:</CreditLabel>
                            <CreditValue>{credits.pending.toLocaleString()}</CreditValue>

                            <CreditLabel>Credits Remaining:</CreditLabel>
                            <CreditValue>{credits.remaining.toLocaleString()}</CreditValue>
                        </CreditsReport>
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
        padding: ${({ theme }) => theme.spacing(0.25, 0.5)};
    }
`;

const ErrorText = styled('span')`
    color: ${({ theme }) => theme.color['error-red-80'].hex};
    margin-left: ${({ theme }) => theme.spacing(0.5)};
`;

const CreditsValue = styled('span')`
    font-weight: 600;
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
    padding: ${({ theme }) => theme.spacing(2.5)};
    max-width: 500px;
    background: ${({ theme }) => theme.color['teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const PopoverHeading = styled('h3')`
    margin: 0;
    font-weight: 700;
    font-size: 1rem;
    line-height: 1.5;
`;

const PopoverSubheading = styled('h4')`
    margin: 0;
`;

const PopoverParagraph = styled('p')`
    margin-top: 0;
    margin-bottom: ${({ theme }) => theme.spacing(2)};
`;

const StyledLink = styled(Link)`
    color: ${({ theme }) => theme.color['green-100'].hex};

    &:hover {
        text-decoration: underline;
    }
`;

const CreditsReport = styled('div')`
    display: grid;
    grid-template-columns: auto auto;
    gap: ${({ theme }) => theme.spacing(0.5, 1)};
    align-items: center;
    justify-content: center;
    padding: ${({ theme }) => theme.spacing(2)};
    border: 1px solid ${({ theme }) => theme.color['green-100'].hex}30;
    border-radius: ${({ theme }) => theme.spacing(1)};
    margin: ${({ theme }) => theme.spacing(2)} auto 0;
`;

const CreditValue = styled('div')`
    font-weight: 600;
    justify-self: end;
`;

const CreditLabel = styled('div')`
    opacity: 0.8;
    font-size: 0.9em;
    text-align: right;
`;
