import { Typography } from '@mui/material';

import EnrollmentStatus from './components/EnrollmentStatus';
import QuestionAndAnswer from './components/QuestionAndAnswer';
import UserProfile from './components/UserProfile';

export default function Home() {
    return (
        <>
            <Typography variant="h1">Skiff NextJS Template</Typography>
            <Typography sx={{ marginBottom: 2 }} component="p">
                This is an example Skiff application that uses{' '}
                <a href="https://nextjs.org">NextJS</a>.
            </Typography>
            <UserProfile />
            <EnrollmentStatus />
            <QuestionAndAnswer />
        </>
    );
}
