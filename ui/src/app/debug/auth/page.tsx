'use client';

import { styled, Typography } from '@mui/material';

import EnrollmentStatus from '@/components/EnrollmentStatus';
import UserProfile from '@/components/UserProfile';

export default function DebugAuthPage() {
    return (
        <Wrapper>
            <Typography variant="h1">Auth Debug</Typography>
            <UserProfile />
            <EnrollmentStatus />
        </Wrapper>
    );
}

const Wrapper = styled('div')`
    background-color: ${({ theme }) => theme.color['cream-100'].hex};
    padding: ${({ theme }) => theme.spacing(3)};
`;
