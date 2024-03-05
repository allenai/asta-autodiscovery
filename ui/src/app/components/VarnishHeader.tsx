'use client';
import { Header } from '@allenai/varnish2/components';
import { PropsWithChildren } from 'react';

export function VarnishHeader({ children }: PropsWithChildren) {
    return (
        <Header>
            <Header.Columns columns="auto 1fr">{children}</Header.Columns>
        </Header>
    );
}

// NextJS doesn't support namespaced exports in server components.
// re-exporting these lets you use them in server components just fine!
export const HeaderLogo = Header.Logo;
export const HeaderAppName = Header.AppName;
export const HeaderAppTagline = Header.AppTagline;
export const HeaderColumns = Header.Columns;
export const HeaderMenuColumn = Header.MenuColumn;
