'use client';

import { useCallback, useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    FormHelperText,
    FormLabel,
    Stack,
    TextField,
    Typography,
    styled,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import LoginOutlinedIcon from '@mui/icons-material/LoginOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import OpenInNewOutlinedIcon from '@mui/icons-material/OpenInNewOutlined';
import LinkOffOutlinedIcon from '@mui/icons-material/LinkOffOutlined';

import {
    CopilotLoginStatus,
    getRunsApi,
    ProviderConfigurationResponseBody,
    ProviderInfo,
} from '@/api/RunsApi';
import { MenuLinks } from '@/components/MenuLinks';
import { useRuntimeConfig } from '@/contexts/RuntimeConfigContext';

export default function SettingsPage() {
    const api = getRunsApi();
    const { isLocal, isLoading: isRuntimeLoading } = useRuntimeConfig();
    const [providers, setProviders] = useState<ProviderInfo[]>([]);
    const [isSigningIn, setIsSigningIn] = useState(false);
    const [copilotLogin, setCopilotLogin] = useState<CopilotLoginStatus | null>(null);
    const [copiedCode, setCopiedCode] = useState(false);
    const [isDisconnecting, setIsDisconnecting] = useState(false);
    const [configuration, setConfiguration] = useState<
        ProviderConfigurationResponseBody['providers'] | null
    >(null);
    const [editingProvider, setEditingProvider] = useState<'openai' | 'vertex' | null>(null);
    const [openaiKey, setOpenaiKey] = useState('');
    const [vertexToken, setVertexToken] = useState('');
    const [vertexProject, setVertexProject] = useState('');
    const [vertexLocation, setVertexLocation] = useState('global');
    const [isSavingProvider, setIsSavingProvider] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadProviders = useCallback(async () => {
        setError(null);
        try {
            const { data: providerData } = await api.getProviders();
            setProviders(providerData.providers);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'Could not check AI providers.'
            );
        }
    }, [api]);

    useEffect(() => {
        const loadInitialSettings = async () => {
            try {
                const { data } = await api.getProviderConfiguration();
                setConfiguration(data.providers);
                setVertexProject(data.providers.vertex.project_id || '');
                setVertexLocation(data.providers.vertex.location || 'global');
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : 'Could not load provider configuration.'
                );
            }
            loadProviders();
        };
        loadInitialSettings();
    }, [api, loadProviders]);

    const startCopilotLogin = async () => {
        setIsSigningIn(true);
        setCopilotLogin(null);
        setCopiedCode(false);
        setError(null);
        try {
            const { data } = await api.startCopilotLogin();
            setCopilotLogin(data);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'Could not open Copilot sign-in.'
            );
            setIsSigningIn(false);
            return;
        }

        const deadline = Date.now() + 2 * 60 * 1000;
        const finishLogin = () => {
            window.clearInterval(statusPoll);
            setIsSigningIn(false);
        };
        const statusPoll = window.setInterval(async () => {
            try {
                const { data: loginData } = await api.getCopilotLoginStatus();
                setCopilotLogin(loginData);
                if (loginData.phase === 'completed') {
                    const [{ data: configurationData }, { data: providerData }] = await Promise.all(
                        [api.getProviderConfiguration(), api.getProviders()]
                    );
                    setConfiguration(configurationData.providers);
                    setProviders(providerData.providers);
                    setCopilotLogin(null);
                    finishLogin();
                } else if (loginData.phase === 'failed' || Date.now() >= deadline) {
                    finishLogin();
                }
            } catch {
                if (Date.now() >= deadline) finishLogin();
            }
        }, 500);
    };

    const copyCopilotCode = async () => {
        if (!copilotLogin?.device_code) return;
        await navigator.clipboard.writeText(copilotLogin.device_code);
        setCopiedCode(true);
    };

    const openCopilotVerification = () => {
        window.open(
            copilotLogin?.verification_url || 'https://github.com/login/device',
            '_blank',
            'noopener,noreferrer'
        );
    };

    const disconnectCopilot = async () => {
        setIsDisconnecting(true);
        setError(null);
        try {
            await api.disconnectCopilot();
            setConfiguration((previous) =>
                previous ? { ...previous, copilot: { configured: false } } : previous
            );
            setProviders((previous) =>
                previous.map((provider) =>
                    provider.id === 'copilot'
                        ? {
                              ...provider,
                              status: 'error',
                              code: 'AUTH_REQUIRED',
                              message: 'Copilot is not connected.',
                              embedding_ready: false,
                              models: [],
                          }
                        : provider
                )
            );
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'Could not disconnect Copilot.'
            );
        } finally {
            setIsDisconnecting(false);
        }
    };

    const saveExternalProvider = async (provider: 'openai' | 'vertex') => {
        setIsSavingProvider(true);
        setError(null);
        try {
            const response =
                provider === 'openai'
                    ? await api.saveProviderConfiguration('openai', { api_key: openaiKey })
                    : await api.saveProviderConfiguration('vertex', {
                          access_token: vertexToken,
                          project_id: vertexProject,
                          location: vertexLocation,
                      });
            const { data } = response;
            setConfiguration(data.providers);
            setOpenaiKey('');
            setVertexToken('');
            setEditingProvider(null);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'Could not save provider configuration.'
            );
        } finally {
            setIsSavingProvider(false);
        }
    };

    const removeExternalProvider = async (provider: 'openai' | 'vertex') => {
        setIsSavingProvider(true);
        setError(null);
        try {
            const { data } = await api.deleteProviderConfiguration(provider);
            setConfiguration(data.providers);
            setEditingProvider(null);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'Could not remove provider configuration.'
            );
        } finally {
            setIsSavingProvider(false);
        }
    };

    if (isRuntimeLoading) {
        return <CenteredProgress />;
    }

    if (!isLocal) {
        return <Alert severity="info">Provider settings are available in the local app.</Alert>;
    }

    const copilot = providers.find((provider) => provider.id === 'copilot');
    const copilotConfigured = configuration?.copilot.configured === true;
    const copilotConnected = copilotConfigured && copilot?.status === 'ready' && !isSigningIn;

    return (
        <Page>
            <Header>
                <Typography component="h1">Settings</Typography>
                <Typography>
                    Connect and check the AI providers available to AutoDiscovery.
                </Typography>
            </Header>

            {error && <Alert severity="error">{error}</Alert>}

            <Section>
                <SectionHeading>AI providers</SectionHeading>
                {!configuration ? (
                    <CenteredProgress />
                ) : (
                    <ProviderList>
                        <ProviderRow>
                            <ProviderSummary>
                                <ProviderName>GitHub Copilot</ProviderName>
                                <ProviderStatus $ready={copilotConnected}>
                                    {copilotConnected ? (
                                        <CheckCircleOutlineIcon fontSize="small" />
                                    ) : (
                                        <ErrorOutlineIcon fontSize="small" />
                                    )}
                                    {copilotConnected
                                        ? 'Connected'
                                        : copilotConfigured
                                          ? 'Signed in · checking connection'
                                          : 'Not connected'}
                                </ProviderStatus>
                                <ProviderMessage>
                                    {copilot?.message || 'Checking Copilot availability…'}
                                </ProviderMessage>
                                {copilotConnected && copilot && (
                                    <ProviderMeta>
                                        {copilot.models.length} models · Embeddings{' '}
                                        {copilot.embedding_ready ? 'available' : 'unavailable'}
                                    </ProviderMeta>
                                )}
                            </ProviderSummary>
                            <ProviderActions>
                                {copilotConfigured ? (
                                    <ActionButton
                                        variant="outlined"
                                        startIcon={<LinkOffOutlinedIcon />}
                                        onClick={disconnectCopilot}
                                        disabled={isSigningIn || isDisconnecting}>
                                        Disconnect
                                    </ActionButton>
                                ) : (
                                    <PrimaryAction
                                        variant="outlined"
                                        startIcon={
                                            isSigningIn ? (
                                                <CircularProgress size={16} />
                                            ) : (
                                                <LoginOutlinedIcon />
                                            )
                                        }
                                        onClick={startCopilotLogin}
                                        disabled={isSigningIn || isDisconnecting}>
                                        Sign in
                                    </PrimaryAction>
                                )}
                            </ProviderActions>
                        </ProviderRow>
                        {isSigningIn && (
                            <LoginPanel>
                                <ProviderName>Connect GitHub Copilot</ProviderName>
                                <ProviderMessage>
                                    Sign into GitHub in the browser, then enter this code when
                                    asked.
                                </ProviderMessage>
                                {copilotLogin?.device_code ? (
                                    <DeviceCode>{copilotLogin.device_code}</DeviceCode>
                                ) : (
                                    <DeviceCodeLoading>
                                        <CircularProgress size={18} /> Preparing code…
                                    </DeviceCodeLoading>
                                )}
                                <LoginActions>
                                    <ActionButton
                                        variant="outlined"
                                        startIcon={<ContentCopyOutlinedIcon />}
                                        onClick={copyCopilotCode}
                                        disabled={!copilotLogin?.device_code}>
                                        {copiedCode ? 'Copied' : 'Copy code'}
                                    </ActionButton>
                                    <PrimaryAction
                                        variant="outlined"
                                        onClick={openCopilotVerification}
                                        startIcon={<OpenInNewOutlinedIcon />}>
                                        Open GitHub
                                    </PrimaryAction>
                                </LoginActions>
                            </LoginPanel>
                        )}

                        {configuration && (
                            <ProviderRow>
                                <ProviderSummary>
                                    <ProviderName>OpenAI</ProviderName>
                                    <ProviderStatus $ready={configuration.openai.configured}>
                                        {configuration.openai.configured ? (
                                            <CheckCircleOutlineIcon fontSize="small" />
                                        ) : (
                                            <ErrorOutlineIcon fontSize="small" />
                                        )}
                                        {configuration.openai.configured
                                            ? 'Configured'
                                            : 'Not configured'}
                                    </ProviderStatus>
                                    <ProviderMessage>
                                        Use an OpenAI API key for GPT models and OpenAI embeddings.
                                    </ProviderMessage>
                                </ProviderSummary>
                                <ProviderActions>
                                    <ActionButton
                                        variant="outlined"
                                        onClick={() => setEditingProvider('openai')}>
                                        {configuration.openai.configured ? 'Update' : 'Configure'}
                                    </ActionButton>
                                    {configuration.openai.configured && (
                                        <RemoveButton
                                            variant="text"
                                            onClick={() => removeExternalProvider('openai')}
                                            disabled={isSavingProvider}>
                                            Remove
                                        </RemoveButton>
                                    )}
                                </ProviderActions>
                            </ProviderRow>
                        )}
                        {editingProvider === 'openai' && (
                            <CredentialForm>
                                <CredentialLabel htmlFor="openai-api-key">
                                    OpenAI API key
                                </CredentialLabel>
                                <CredentialField
                                    id="openai-api-key"
                                    type="password"
                                    value={openaiKey}
                                    onChange={(event) => setOpenaiKey(event.target.value)}
                                    autoComplete="off"
                                    placeholder="sk-…"
                                />
                                <CredentialHelp>
                                    Stored in macOS Keychain. The key is never returned to the UI.
                                </CredentialHelp>
                                <FormActions>
                                    <ActionButton onClick={() => setEditingProvider(null)}>
                                        Cancel
                                    </ActionButton>
                                    <PrimaryAction
                                        variant="outlined"
                                        onClick={() => saveExternalProvider('openai')}
                                        disabled={!openaiKey.trim() || isSavingProvider}>
                                        Save OpenAI
                                    </PrimaryAction>
                                </FormActions>
                            </CredentialForm>
                        )}

                        {configuration && (
                            <ProviderRow>
                                <ProviderSummary>
                                    <ProviderName>Google Vertex AI</ProviderName>
                                    <ProviderStatus $ready={configuration.vertex.configured}>
                                        {configuration.vertex.configured ? (
                                            <CheckCircleOutlineIcon fontSize="small" />
                                        ) : (
                                            <ErrorOutlineIcon fontSize="small" />
                                        )}
                                        {configuration.vertex.configured
                                            ? 'Configured'
                                            : 'Not configured'}
                                    </ProviderStatus>
                                    <ProviderMessage>
                                        Use a Vertex access token, project, and location for Gemini.
                                    </ProviderMessage>
                                </ProviderSummary>
                                <ProviderActions>
                                    <ActionButton
                                        variant="outlined"
                                        onClick={() => setEditingProvider('vertex')}>
                                        {configuration.vertex.configured ? 'Update' : 'Configure'}
                                    </ActionButton>
                                    {configuration.vertex.configured && (
                                        <RemoveButton
                                            variant="text"
                                            onClick={() => removeExternalProvider('vertex')}
                                            disabled={isSavingProvider}>
                                            Remove
                                        </RemoveButton>
                                    )}
                                </ProviderActions>
                            </ProviderRow>
                        )}
                        {editingProvider === 'vertex' && (
                            <CredentialForm>
                                <CredentialLabel htmlFor="vertex-access-token">
                                    Vertex access token
                                </CredentialLabel>
                                <CredentialField
                                    id="vertex-access-token"
                                    type="password"
                                    value={vertexToken}
                                    onChange={(event) => setVertexToken(event.target.value)}
                                    autoComplete="off"
                                />
                                <CredentialLabel htmlFor="vertex-project-id">
                                    Project ID
                                </CredentialLabel>
                                <CredentialField
                                    id="vertex-project-id"
                                    value={vertexProject}
                                    onChange={(event) => setVertexProject(event.target.value)}
                                />
                                <CredentialLabel htmlFor="vertex-location">
                                    Location
                                </CredentialLabel>
                                <CredentialField
                                    id="vertex-location"
                                    value={vertexLocation}
                                    onChange={(event) => setVertexLocation(event.target.value)}
                                    placeholder="global"
                                />
                                <CredentialHelp>
                                    Stored in macOS Keychain. Access tokens expire and may need to
                                    be updated.
                                </CredentialHelp>
                                <FormActions>
                                    <ActionButton onClick={() => setEditingProvider(null)}>
                                        Cancel
                                    </ActionButton>
                                    <PrimaryAction
                                        variant="outlined"
                                        onClick={() => saveExternalProvider('vertex')}
                                        disabled={
                                            !vertexToken.trim() ||
                                            !vertexProject.trim() ||
                                            isSavingProvider
                                        }>
                                        Save Vertex AI
                                    </PrimaryAction>
                                </FormActions>
                            </CredentialForm>
                        )}
                    </ProviderList>
                )}
            </Section>

            <Section>
                <SectionHeading>Resources & policies</SectionHeading>
                <PolicyLinks>
                    <MenuLinks layout="settings" />
                </PolicyLinks>
            </Section>
        </Page>
    );
}

const Page = styled(Stack)(({ theme }) => ({
    gap: theme.spacing(3),
    margin: '0 auto',
    maxWidth: 900,
    padding: theme.spacing(3),
}));

const Header = styled(Box)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    '& h1': {
        color: theme.color['green-100'].hex,
        fontSize: '1.5rem',
        fontWeight: 700,
        marginBottom: theme.spacing(0.5),
    },
}));

const Section = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    borderRadius: 8,
    padding: theme.spacing(3),
}));

const SectionHeading = styled(Typography)(({ theme }) => ({
    color: theme.color['green-40'].hex,
    fontSize: '1rem',
    fontWeight: 700,
    marginBottom: theme.spacing(2),
}));

const ProviderList = styled(Stack)(({ theme }) => ({
    gap: theme.spacing(0),
}));

const CredentialForm = styled(Stack)(({ theme }) => ({
    borderTop: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    gap: theme.spacing(1),
    padding: theme.spacing(2, 0, 3),
}));

const LoginPanel = styled(Stack)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    border: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    borderRadius: 4,
    gap: theme.spacing(1),
    margin: theme.spacing(0, 0, 2),
    padding: theme.spacing(2),
}));

const DeviceCode = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    fontFamily: 'monospace',
    fontSize: '1.5rem',
    fontWeight: 700,
    letterSpacing: 0,
    marginTop: theme.spacing(1),
}));

const DeviceCodeLoading = styled(Box)(({ theme }) => ({
    alignItems: 'center',
    color: theme.color['cream-60'].rgba.toString(),
    display: 'flex',
    gap: theme.spacing(1),
    marginTop: theme.spacing(1),
}));

const LoginActions = styled(Stack)(({ theme }) => ({
    flexDirection: 'row',
    gap: theme.spacing(1),
    marginTop: theme.spacing(1),
}));

const CredentialLabel = styled(FormLabel)(({ theme }) => ({
    color: theme.color['green-40'].hex,
    fontWeight: 700,
    marginTop: theme.spacing(1),
}));

const CredentialField = styled(TextField)(({ theme }) => ({
    '& .MuiOutlinedInput-root': {
        color: theme.color['cream-100'].hex,
        '& fieldset': { borderColor: theme.color['cream-20'].rgba.toString() },
        '&:hover fieldset, &.Mui-focused fieldset': {
            borderColor: theme.color['green-100'].hex,
        },
    },
}));

const CredentialHelp = styled(FormHelperText)(({ theme }) => ({
    color: theme.color['cream-60'].rgba.toString(),
    margin: theme.spacing(0.5, 0, 0),
}));

const FormActions = styled(Stack)(({ theme }) => ({
    flexDirection: 'row',
    gap: theme.spacing(1),
    justifyContent: 'flex-end',
    marginTop: theme.spacing(1),
}));

const ProviderRow = styled(Box)(({ theme }) => ({
    alignItems: 'center',
    borderTop: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    display: 'flex',
    gap: theme.spacing(3),
    justifyContent: 'space-between',
    padding: theme.spacing(2, 0),
    '&:first-of-type': { borderTop: 0, paddingTop: 0 },
    '@media (max-width: 700px)': { alignItems: 'stretch', flexDirection: 'column' },
}));

const ProviderSummary = styled(Box)({ minWidth: 0 });

const ProviderName = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    fontWeight: 700,
}));

const ProviderStatus = styled(Box, {
    shouldForwardProp: (prop) => prop !== '$ready',
})<{ $ready: boolean }>(({ theme, $ready }) => ({
    alignItems: 'center',
    color: $ready ? theme.color['green-100'].hex : theme.color['cream-60'].rgba.toString(),
    display: 'flex',
    fontSize: '0.875rem',
    gap: theme.spacing(0.75),
    marginTop: theme.spacing(0.75),
}));

const ProviderMessage = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    fontSize: '0.875rem',
    marginTop: theme.spacing(0.75),
}));

const ProviderMeta = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-60'].rgba.toString(),
    fontSize: '0.875rem',
    marginTop: theme.spacing(0.5),
}));

const ProviderActions = styled(Stack)(({ theme }) => ({
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    flexShrink: 0,
    gap: theme.spacing(1),
    justifyContent: 'flex-end',
}));

const ActionButton = styled(Button)(({ theme }) => ({
    '&&': {
        backgroundColor: 'transparent',
        border: `1px solid ${theme.color['cream-20'].rgba.toString()}`,
        borderRadius: 4,
        color: theme.color['cream-100'].hex,
        height: 40,
        padding: theme.spacing(0, 2),
        '&:hover': {
            backgroundColor: 'transparent',
            borderColor: theme.color['cream-40'].rgba.toString(),
            color: theme.color['green-100'].hex,
        },
        '&.Mui-disabled': {
            borderColor: theme.color['cream-10'].rgba.toString(),
            color: theme.color['cream-40'].rgba.toString(),
        },
    },
}));

const PrimaryAction = styled(Button)(({ theme }) => ({
    '&&': {
        backgroundColor: 'transparent',
        border: `1px solid ${theme.color['green-40'].rgba.toString()}`,
        borderRadius: 4,
        color: theme.color['cream-100'].hex,
        height: 40,
        padding: theme.spacing(0, 2),
        '&:hover': {
            backgroundColor: 'transparent',
            borderColor: theme.color['green-100'].hex,
            color: theme.color['green-100'].hex,
        },
        '&.Mui-disabled': {
            borderColor: theme.color['cream-10'].rgba.toString(),
            color: theme.color['cream-40'].rgba.toString(),
        },
    },
}));

const RemoveButton = styled(Button)(({ theme }) => ({
    '&&': {
        color: theme.color['error-red-60'].hex,
        height: 40,
        padding: theme.spacing(0, 1.5),
    },
}));

const PolicyLinks = styled(Box)(({ theme }) => ({
    '& > div': {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
        padding: 0,
    },
    '& > div + div': { borderTop: 0 },
    '& a, & button': {
        borderBottom: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
        color: theme.color['cream-80'].rgba.toString(),
    },
    '@media (max-width: 700px)': {
        '& > div': { gridTemplateColumns: '1fr' },
    },
}));

function CenteredProgress() {
    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
        </Box>
    );
}
