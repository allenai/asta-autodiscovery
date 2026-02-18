import { Box, Typography, styled, Button } from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';

import { filterTransientProps } from '@/utils/styledProps';

interface IntroBoxProps {
    showLogin?: boolean;
    onLoginClick?: () => void;
}

export const IntroBox = ({ showLogin = false, onLoginClick }: IntroBoxProps) => {
    return (
        <Wrapper $showLogin={showLogin}>
            <Title>AutoDiscovery</Title>
            <Subtitle>Uncover surprising insights hidden in your data.</Subtitle>
            <Description>
                AutoDiscovery uses <strong>Bayesian surprise</strong> to autonomously explore your
                datasets. It identifies discoveries that genuinely change what we know, challenging
                assumptions to inspire entirely new lines of inquiry.
            </Description>
            {showLogin && (
                <LoginButton onClick={onLoginClick} variant="contained" endIcon={<LoginIcon />}>
                    Sign in to get started
                </LoginButton>
            )}
        </Wrapper>
    );
};

const Wrapper = styled(Box, {
    shouldForwardProp: filterTransientProps,
})<{ $showLogin: boolean }>(({ theme, $showLogin }) => ({
    background: `radial-gradient(155.14% 72.67% at 50% 100%, rgba(36, 84, 85, 0.4) 0%, rgba(36, 84, 85, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%), #162D31`,
    border: '1px solid rgba(250, 242, 233, 0.30)',
    borderColor:
        'radial-gradient(155.14% 72.67% at 50% 100%, rgba(36, 84, 85, 0.4) 0%, rgba(36, 84, 85, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%);',
    borderRadius: theme.spacing(1.5),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    marginTop: $showLogin ? '72px' : 0,
    padding: theme.spacing(4.5),
    container: 'intro-box / inline-size',
}));

const Title = styled(Typography)(({ theme }) => ({
    color: theme.color['green-100'].hex,
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: '2.5rem',
    fontWeight: 700,
    lineHeight: '1.15',
    marginBottom: '4px',

    '@container intro-box (width < 400px)': {
        fontSize: '14cqw',
        lineHeight: '1.15',
    },
}));

const Subtitle = styled(Typography)(() => ({
    color: '#FAF2E9',
    fontFamily: 'Manrope, sans-serif',
    fontSize: '24px',
    fontStyle: 'normal',
    fontWeight: 400,
    lineHeight: '1.5',

    '@container intro-box (width < 400px)': {
        fontSize: '12cqw',
        lineHeight: '1.1',
    },
}));

const Description = styled(Typography)(({ theme }) => ({
    maxWidth: '600px',
    marginTop: theme.spacing(2),
    fontFamily: 'Manrope',
    fontSize: '1.125rem',
    fontWeight: 400,
    lineHeight: '1.5',

    '@container intro-box (width < 400px)': {
        fontSize: '9cqw',
        lineHeight: '1.3',
    },
}));

const LoginButton = styled(Button)(({ theme }) => ({
    backgroundColor: theme.color['green-100'].hex,
    color: theme.color['extra-dark-teal-100'].hex,
    marginTop: theme.spacing(3),
    padding: theme.spacing(1.5, 3),
    fontFamily: 'Manrope',
    fontSize: '1rem',
    fontWeight: 500,
    lineHeight: '100%',
    textTransform: 'none',
    '&:hover': {
        backgroundColor: theme.color['green-80'].hex,
    },
}));
