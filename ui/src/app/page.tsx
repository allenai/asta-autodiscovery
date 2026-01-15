import { Link, Typography } from '@mui/material';

import EnrollmentStatus from './components/EnrollmentStatus';
import UserProfile from './components/UserProfile';

export default function Home() {
    return (
        <>
            <Typography variant="h1">AutoDiscovery</Typography>
            <Typography sx={{ marginBottom: 2 }} component="p">
                Get started over at <Link href="/runs">/runs</Link>
            </Typography>
            <UserProfile />
            <EnrollmentStatus />
        </>
    );
}
