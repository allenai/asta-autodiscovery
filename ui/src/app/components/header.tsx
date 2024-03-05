import { SimpleLogo } from './SimpleLogo';
import { HeaderAppName, HeaderLogo, VarnishHeader } from './VarnishHeader';

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
        </VarnishHeader>
    );
}
