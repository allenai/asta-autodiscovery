'use client';

import { Button, styled } from '@mui/material';
import LoginOutlinedIcon from '@mui/icons-material/LoginOutlined';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';

import { useAuth0 } from '@/contexts/Auth0Context';

export default function AuthButton() {
    const { isAuthenticated, isLoading, loginWithRedirect, logout } = useAuth0();

    const handleLogout = () => {
        logout();
    };

    if (isLoading) {
        return null;
    }

    return (
        <StyledButton
            onClick={isAuthenticated ? handleLogout : loginWithRedirect}
            variant="outlined"
            endIcon={isAuthenticated ? <LogoutOutlinedIcon /> : <LoginOutlinedIcon />}>
            {isAuthenticated ? 'Logout' : 'Login'}
        </StyledButton>
    );
}

const StyledButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};

        & .MuiButton-endIcon {
            margin: 0 0 0 ${({ theme }) => theme.spacing(0.75)};
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};

        &:hover {
            border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        }
    }
`;
