'use client';

import { useRef, useState } from 'react';
import { Chip, Popover, styled } from '@mui/material';
import Link from 'next/link';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { mkCreditsBtnTrackAttrs } from '@/analytics/run';

export default function CreditsChip() {
    const { credits, lastError, isLoadingInitial } = useViewerCredits();
    const [isOpen, setIsOpen] = useState(false);

    const anchorRef = useRef<HTMLDivElement | null>(null);

    return (
        <>
            <StyledChip
                ref={anchorRef}
                label={
                    <span>
                        <DesktopOnly>Experiment </DesktopOnly>Credits:{' '}
                        {lastError ? (
                            <ErrorText>Error</ErrorText>
                        ) : isLoadingInitial ? (
                            <LoadingShimmer />
                        ) : (
                            <CreditsValue>{credits?.available.toLocaleString()}</CreditsValue>
                        )}
                    </span>
                }
                onClick={() => setIsOpen(!isOpen)}
                {...mkCreditsBtnTrackAttrs()}
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
                        To support your research, we are providing up to{' '}
                        <strong>500 credits</strong> per user to run experiments.
                    </PopoverParagraph>
                    <ul>
                        <li>
                            <strong>Exchange Rate:</strong> 1 Credit = 1 Experiment.
                        </li>
                        <li>
                            <strong>Budget Protection:</strong> We recommend starting with a small
                            budget ({'<'}10) to learn how the system works. Once you're familiar
                            with the output, you can confidently scale up to 5-100 experiments per
                            session.
                        </li>
                        <li>
                            <strong>Early User Benefit:</strong> If you signed up before Feb 28,
                            2026 and still have more than 500 credits remaining, you keep your full
                            balance. That's your reward for being here early.
                        </li>
                        <li>
                            <strong>Expiration:</strong> Credits are valid until{' '}
                            <strong>May 31, 2026</strong>.
                        </li>
                    </ul>

                    <PopoverSubheading>Can I get more credits?</PopoverSubheading>
                    <PopoverParagraph>
                        Credits are a fixed allocation to support public access for scientific and
                        educational purposes. If you've exhausted your credits and your work is
                        producing promising results, we want to hear about it. If you are interested
                        in discussing potential research collaborations to further scientific
                        discovery, please contact us at{' '}
                        <StyledLink href="mailto:asta-support@allenai.org">
                            asta-support@allenai.org
                        </StyledLink>
                        .
                    </PopoverParagraph>

                    {isLoadingInitial ? (
                        <LoadingShimmer />
                    ) : credits !== null ? (
                        <CreditsReport>
                            <CreditLabel>Credits Consumed:</CreditLabel>
                            <CreditValue>{credits.consumed.toLocaleString()}</CreditValue>

                            <CreditLabel>Credits Pending:</CreditLabel>
                            <CreditValue>{credits.pending.toLocaleString()}</CreditValue>

                            <CreditLabel>Credits Available:</CreditLabel>
                            <CreditValue>{credits.available.toLocaleString()}</CreditValue>
                        </CreditsReport>
                    ) : null}
                </PopoverContent>
            </Popover>
        </>
    );
}

const DesktopOnly = styled('span')`
    @media (max-width: 600px) {
        display: none;
    }
`;

const StyledChip = styled(Chip)`
    &.MuiChip-root {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
        border-radius: 4px;
        color: ${({ theme }) => theme.color['cream-100'].hex};
        font-size: 0.85rem;
        padding: ${({ theme }) => theme.spacing(0.25, 0.5)};
        white-space: nowrap;
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
