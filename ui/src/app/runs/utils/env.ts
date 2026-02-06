export function isBrowser(win: Window = globalThis.window): win is Window {
    return win instanceof Window;
}
