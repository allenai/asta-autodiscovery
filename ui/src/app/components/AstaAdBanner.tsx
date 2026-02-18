'use client';

import { useState, useEffect } from 'react';
import { Box, Typography } from '@mui/material';
import { lighten } from '@mui/material/styles';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import Image from 'next/image';

export const AstaAdBanner = () => {
    const [showBanner, setShowBanner] = useState(false);
    const [shouldAnimate, setShouldAnimate] = useState(true);

    useEffect(() => {
        const hasSeenBanner = localStorage.getItem('astaBannerSeen') === 'true';

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

    return (
        <Box
            onClick={() => window.open('https://asta.example.com?utm_source=AutoDiscovery', '_blank')}
            sx={{
                position: 'fixed',
                bottom: showBanner ? '96px' : '-200px',
                left: '50%',
                transform: 'translateX(-50%)',
                maxWidth: '800px',
                width: 'calc(100% - 32px)',
                padding: '18px',
                borderRadius: '4px',
                backgroundColor: (theme) => theme.color['teal-100'].hex,
                cursor: 'pointer',
                transition: shouldAnimate
                    ? 'bottom 0.5s ease-out, background-color 250ms ease-out'
                    : 'background-color 250ms ease-out',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                '&:hover': {
                    backgroundColor: (theme) => lighten(theme.color['teal-100'].hex, 0.1),
                    '& .arrow-icon': {
                        color: (theme) => theme.color['green-100'].hex,
                    },
                },
            }}>
            <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                <Image src="/asta-logo.svg" alt="Asta" width={75} height={18} />
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
                }}
            />
        </Box>
    );
};
