'use client';

import { Button, Popover, styled } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import { useState } from 'react';

import { MenuLinks } from './MenuLinks';
import { useAuth0 } from '@/contexts/Auth0Context';
import { mkLogoutBtnTrackAttrs, mkUserMenuBtnTrackAttrs } from '@/analytics/run';
import { TEST_ID_SIGN_OUT_BUTTON, TEST_ID_USER_MENU_BUTTON } from '@/testIds';

/**
 * Sidebar footer: a user-profile button that opens a popover menu with the
 * app's policy/feedback links and a Sign Out action. Mirrors the Asta footer.
 */
export const UserMenuFooter = () => {
    const { user, logout } = useAuth0();
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

    const displayName = user?.name || user?.email || 'User';
    const avatarLetter = displayName.charAt(0).toUpperCase() || 'U';

    return (
        <FooterWrapper>
            <UserProfileButton
                onClick={(event) => setAnchorEl(event.currentTarget)}
                data-test-id={TEST_ID_USER_MENU_BUTTON}
                {...mkUserMenuBtnTrackAttrs()}>
                <UserAvatar>{avatarLetter}</UserAvatar>
                <UserName>{displayName}</UserName>
                <MoreVertIcon />
            </UserProfileButton>

            <StyledPopover
                open={Boolean(anchorEl)}
                anchorEl={anchorEl}
                onClose={() => setAnchorEl(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
                transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}>
                <PopoverContent>
                    <MenuLinks />
                    <SignOutSection>
                        <SignOutButton
                            type="button"
                            onClick={() => logout()}
                            data-test-id={TEST_ID_SIGN_OUT_BUTTON}
                            {...mkLogoutBtnTrackAttrs()}>
                            Sign Out
                            <LogoutOutlinedIcon />
                        </SignOutButton>
                    </SignOutSection>
                </PopoverContent>
            </StyledPopover>
        </FooterWrapper>
    );
};

const FooterWrapper = styled('div')`
    border-top: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    padding: ${({ theme }) => theme.spacing(1.5)};
`;

const UserProfileButton = styled(Button)`
    &.MuiButton-root {
        align-items: center;
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
        border-radius: ${({ theme }) => theme.shape.borderRadius}px;
        color: ${({ theme }) => theme.color['cream-100'].hex};
        display: flex;
        gap: ${({ theme }) => theme.spacing(1.5)};
        justify-content: space-between;
        padding: ${({ theme }) => theme.spacing(1.5, 2)};
        text-transform: none;
        width: 100%;

        &:hover {
            background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
        }

        & .MuiSvgIcon-root {
            color: ${({ theme }) => theme.color['cream-40'].rgba.toString()};
            font-size: 1.25rem;
        }
    }
`;

const UserAvatar = styled('div')`
    align-items: center;
    background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    flex-shrink: 0;
    font-weight: 600;
    height: ${({ theme }) => theme.spacing(4)};
    justify-content: center;
    width: ${({ theme }) => theme.spacing(4)};
`;

const UserName = styled('span')`
    flex: 1;
    overflow: hidden;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
`;

const StyledPopover = styled(Popover)`
    & .MuiPaper-root {
        background: ${({ theme }) => theme.color['teal-100'].hex};
        border-radius: 4px;
        width: 280px;
    }
`;

const PopoverContent = styled('div')`
    display: flex;
    flex-direction: column;
`;

const SignOutSection = styled('div')`
    border-top: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    display: flex;
    flex-direction: column;
    padding: ${({ theme }) => theme.spacing(0.5)};
`;

const SignOutButton = styled('button')`
    align-items: center;
    background: none;
    border: none;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    cursor: pointer;
    display: flex;
    font-family: inherit;
    font-size: 14px;
    gap: ${({ theme }) => theme.spacing(1)};
    padding: ${({ theme }) => theme.spacing(1.5)};
    text-align: left;
    transition: color 250ms ease-in-out;

    &:hover,
    &:focus-visible {
        color: ${({ theme }) => theme.color['cream-60'].rgba.toString()};
    }

    & .MuiSvgIcon-root {
        font-size: 1.125rem;
    }
`;
