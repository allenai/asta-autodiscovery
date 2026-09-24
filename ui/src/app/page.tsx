import { styled } from '@mui/material';
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import { useRouter } from '@/router';

export default function HomePage() {
    const router = useRouter();
    const { search, hash } = useLocation();

    useEffect(() => {
        // Keep the query string. Auth0 redirects back to `/` with `code` and `state`,
        // and the auth provider only reads them once its runtime config has loaded.
        // Dropping them here would silently abandon the login.
        router.replace(`/runs${search}${hash}`);
    }, [router, search, hash]);

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
