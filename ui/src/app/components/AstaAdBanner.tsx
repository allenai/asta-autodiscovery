'use client';

import { useState, useEffect } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import { lighten } from '@mui/material/styles';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CloseIcon from '@mui/icons-material/Close';
import Image from 'next/image';

type AstaAdBannerProps = {
    isFullWidth?: boolean;
};

export const AstaAdBanner = ({ isFullWidth = false }: AstaAdBannerProps) => {
    const [showBanner, setShowBanner] = useState(false);
    const [shouldAnimate, setShouldAnimate] = useState(true);

    useEffect(() => {
        const hasSeenBanner = localStorage.getItem('astaBannerSeen') === 'true';
        const hasDismissedBanner = localStorage.getItem('astaBannerDismissed') === 'true';

        // Don't show if user has dismissed it
        if (hasDismissedBanner) {
            return;
        }

        if (hasSeenBanner) {
            // Already seen - show immediately without animation
            setShouldAnimate(false);
            setShowBanner(true);
        } else {
            // First time - show with animation after delay
            const timer = setTimeout(() => {
                setShowBanner(true);
                localStorage.setItem('astaBannerSeen', 'true');
            }, 1000);

            return () => clearTimeout(timer);
        }
    }, []);

    const handleClose = (e: React.MouseEvent) => {
        e.stopPropagation();
        localStorage.setItem('astaBannerDismissed', 'true');
        setShowBanner(false);
    };

    return (
        <Box
            onClick={() => window.open('https://asta.example.com?utm_source=AutoDiscovery', '_blank')}
            sx={{
                position: 'fixed',
                bottom: showBanner ? '0' : '-200px',
                left: '50%',
                transform: 'translateX(-50%)',
                maxWidth: isFullWidth ? 'none' : '800px',
                width: isFullWidth ? '100%' : 'calc(100% - 32px)',
                padding: '18px',
                borderRadius: isFullWidth ? '0' : '4px 4px 0 0',
                backgroundColor: (theme) => theme.color['teal-100'].hex,
                cursor: 'pointer',
                transition: shouldAnimate
                    ? 'bottom 0.5s ease-out, background-color 250ms ease-out'
                    : 'background-color 250ms ease-out',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                '@media (max-width: 600px)': {
                    alignItems: 'flex-start',
                    width: '100%',
                },
                '&:hover': {
                    backgroundColor: (theme) => lighten(theme.color['teal-100'].hex, 0.1),
                    '& .arrow-icon': {
                        color: (theme) => theme.color['green-100'].hex,
                    },
                },
            }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                <IconButton
                    onClick={handleClose}
                    sx={{
                        color: (theme) => theme.color['cream-100'].hex,
                        padding: '4px',
                        flexShrink: 0,
                        '&:hover': {
                            backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        },
                    }}>
                    <CloseIcon sx={{ fontSize: '20px' }} />
                </IconButton>
                <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                    <Image src="/asta-logo.svg" alt="Asta" width={75} height={18} />
                </Box>
            </Box>
            <Typography
                sx={{
                    fontFamily: '"Manrope", sans-serif',
                    fontSize: '16px',
                    color: (theme) => theme.color['cream-100'].hex,
                    lineHeight: '1.5',
                    flex: 1,
                    margin: 0,
                }}>
                Try Asta, a scholarly research assistant from Ai2
            </Typography>
            <ArrowForwardIcon
                className="arrow-icon"
                sx={{
                    color: (theme) => theme.color['cream-100'].hex,
                    transition: 'color 250ms ease-out',
                    fontSize: '20px',
                    flexShrink: 0,
                    '@media (max-width: 600px)': {
                        display: 'none',
                    },
                }}
            />
        </Box>
    );
};
