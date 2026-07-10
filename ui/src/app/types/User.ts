import { UserFromApi } from '@/api/UserApi';

export type User = {
    sub: string;
    name: string;
    email: string;
    picture: string;
    emailVerified: boolean;
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
