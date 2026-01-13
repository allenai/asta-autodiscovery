'use client';

import { Button, Avatar, Box, Typography, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';
import { useAuth0 } from '../contexts/Auth0Context';

export default function AuthButton() {
    const { isAuthenticated, isLoading, user, loginWithRedirect, logout } = useAuth0();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        handleClose();
        logout();
    };

    if (isLoading) {
        return null;
    }

    if (!isAuthenticated) {
        return (
            <Button
                variant="contained"
                color="primary"
                onClick={loginWithRedirect}
            >
                Log In
            </Button>
        );
    }

    return (
        <>
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    '&:hover': { opacity: 0.8 }
                }}
                onClick={handleClick}
            >
                <Avatar
                    src={user?.picture}
                    alt={user?.name}
                    sx={{ width: 32, height: 32, mr: 1 }}
                />
                <Typography variant="body2">{user?.name}</Typography>
            </Box>
            <Menu
                anchorEl={anchorEl}
                open={open}
                onClose={handleClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                <MenuItem onClick={handleLogout}>Log Out</MenuItem>
            </Menu>
        </>
    );
}
