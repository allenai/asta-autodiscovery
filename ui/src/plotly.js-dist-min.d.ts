declare module 'plotly.js-dist-min' {
    const Plotly: {
        react: (
            root: HTMLElement,
            data: unknown,
            layout?: unknown,
            config?: unknown
        ) => Promise<unknown> | unknown;
        purge: (root: HTMLElement) => void;
    };

    export default Plotly;
}
