import { forwardRef, useMemo, type AnchorHTMLAttributes } from 'react';
import {
    Link as RouterLink,
    useLocation,
    useNavigate,
    useParams,
    useSearchParams as useRouterSearchParams,
} from 'react-router-dom';

export { useParams };

// Thin adapter so pages keep a `router.push/replace` + `<Link href>` API on top of React Router.
export function useRouter() {
    const navigate = useNavigate();
    return useMemo(
        () => ({
            push: (to: string) => navigate(to),
            replace: (to: string, _opts?: { scroll?: boolean }) => navigate(to, { replace: true }),
            back: () => navigate(-1),
        }),
        [navigate]
    );
}

export function usePathname(): string {
    return useLocation().pathname;
}

export function useSearchParams(): URLSearchParams {
    return useRouterSearchParams()[0];
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

// External and new-tab links stay plain anchors; in-app links use client-side navigation.
export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link({ href, ...rest }, ref) {
    if (/^[a-z]+:/i.test(href) || rest.target === '_blank') {
        return <a ref={ref} href={href} {...rest} />;
    }
    return <RouterLink ref={ref} to={href} {...rest} />;
});
