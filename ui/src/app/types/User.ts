import { GetViewerEnrollmentResponseBody, UserFromApi } from '@/api/UserApi';

export type User = {
    sub: string;
    name: string;
    email: string;
    picture: string;
    emailVerified: boolean;
};

export type EnrollmentState = {
    enrolled: boolean;
    enrollmentDate: string | null;
    status: string | null;
    experimentsCount: number | null;
    userId: string | null;
};

export function getUserFromApi(userFromApi: UserFromApi): User {
    return {
        sub: userFromApi.sub,
        name: userFromApi.name,
        email: userFromApi.email,
        picture: userFromApi.picture,
        emailVerified: userFromApi.email_verified,
    };
}

export function getEnrollmentStateFromApi(
    responseBody: GetViewerEnrollmentResponseBody
): EnrollmentState {
    return {
        enrolled: responseBody.enrolled,
        enrollmentDate: responseBody.enrollment_date,
        status: responseBody.status,
        experimentsCount: responseBody.experiments_count,
        userId: responseBody.user_id,
    };
}
