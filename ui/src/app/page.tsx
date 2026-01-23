'use client';

import { styled } from '@mui/material';
import { useRouter } from 'next/dist/client/components/navigation';
import { useEffect } from 'react';

export default function HomePage() {
    const router = useRouter();

    useEffect(() => {
        router.replace('/runs');
    }, [router]);

    return <LoadingScreen />;
}

const LoadingScreen = styled('div')`
    align-items: center;
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    display: flex;
    height: 100vh;
    justify-content: center;
    width: 100vw;
`;
