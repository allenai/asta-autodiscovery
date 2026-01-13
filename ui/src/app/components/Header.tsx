'use client';

import { Box } from '@mui/material';
import { SimpleLogo } from './SimpleLogo';
import { HeaderAppName, HeaderLogo, VarnishHeader } from './VarnishHeader';
import AuthButton from './AuthButton';

export default function Header() {
    return (
        <VarnishHeader>
            <HeaderLogo label={<HeaderAppName>Next Skiff Template</HeaderAppName>}>
                <SimpleLogo>
                    <span role="img" aria-label="Simple Logo">
                        ⛵️
                    </span>
                </SimpleLogo>
            </HeaderLogo>
            <Box sx={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
                <AuthButton />
            </Box>
        </VarnishHeader>
    );
}
