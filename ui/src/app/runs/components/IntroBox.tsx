import { Box, Typography, styled, Button } from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';

interface IntroBoxProps {
    showLogin?: boolean;
    onLoginClick?: () => void;
}

export const IntroBox = ({ showLogin = false, onLoginClick }: IntroBoxProps) => {
    return (
        <Wrapper>
            <Title>AutoDiscovery</Title>
            <Subtitle>Uncover surprising insights hidden in your data.</Subtitle>
            <Description>
                AutoDiscovery uses <strong>Bayesian surprise</strong> (a measure of how much new
                experimental evidence shifts our beliefs) to autonomously explore your datasets. It
                identifies discoveries that genuinely change what we know, challenging assumptions
                to inspire entirely new lines of inquiry.
            </Description>
            {showLogin && (
                <>
                    <LoginHeading>Sign in to continue</LoginHeading>
                    <LoginDescription>
                        Your datasets and discoveries are kept private and secure. Signing in
                        ensures that only you can access your research.
                    </LoginDescription>
                    <LoginButton onClick={onLoginClick} variant="contained" endIcon={<LoginIcon />}>
                        Sign in to get started
                    </LoginButton>
                </>
            )}
        </Wrapper>
    );
};

const Wrapper = styled(Box)(({ theme }) => ({
    background: `radial-gradient(155.14% 72.67% at 0% 0%, rgba(255, 163, 28, 0.10) 0%, rgba(255, 163, 28, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%)`,
    border: '1px solid rgba(250, 242, 233, 0.30)',
    borderColor:
        'radial-gradient(155.14% 72.67% at 0% 0%, rgba(255, 163, 28, 0.10) 0%, rgba(255, 163, 28, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%);',
    borderRadius: theme.spacing(1.5),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    padding: theme.spacing(4.5),
}));

const Title = styled(Typography)(({ theme }) => ({
    color: theme.color['green-100'].hex,
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: '2.5rem',
    fontWeight: 700,
    lineHeight: '115%',
    marginBottom: '4px',
}));

const Subtitle = styled(Typography)(() => ({
    color: '#FAF2E9',
    fontFamily: 'Manrope',
    fontSize: '1.5rem',
    fontWeight: 400,
    lineHeight: '1.5rem',
}));

const Description = styled(Typography)(({ theme }) => ({
    maxWidth: '600px',
    marginTop: theme.spacing(2),
    fontFamily: 'Manrope',
    fontSize: '1.125rem',
    fontWeight: 400,
    lineHeight: '150%',
}));

const LoginHeading = styled(Typography)(({ theme }) => ({
    color: '#9FEAD1',
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: '1.5rem',
    fontWeight: 700,
    lineHeight: '115%',
    marginTop: theme.spacing(4),
    marginBottom: theme.spacing(1),
}));

const LoginDescription = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    fontFamily: 'Manrope',
    fontSize: '1rem',
    fontWeight: 400,
    lineHeight: '150%',
    marginBottom: theme.spacing(3),
}));

const LoginButton = styled(Button)(({ theme }) => ({
    backgroundColor: theme.color['green-100'].hex,
    color: theme.color['extra-dark-teal-100'].hex,
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
