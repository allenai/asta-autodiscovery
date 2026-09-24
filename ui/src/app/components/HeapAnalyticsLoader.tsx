
import { useEffect, useState } from 'react';

import { useAuth0 } from '@/contexts/Auth0Context';

const projectId = import.meta.env.PROD ? 1887597889 : 2426822886;

// TypeScript declarations for Heap
declare global {
    interface Window {
        heap?: {
            identify: (identifier: string) => void;
            addUserProperties: (properties: Record<string, any>) => void;
            addEventProperties: (properties: Record<string, any>) => void;
        };
    }
}

export default function HeapAnalyticsLoader() {
    const [scriptLoaded, setScriptLoaded] = useState(false);
    const { user } = useAuth0(); // Assuming useAuth is a custom hook to get auth status and session

    useEffect(() => {
        if (!window.heap) {
            return;
        }

        if (user && user.email) {
            window.heap.identify(user.email);
            window.heap.addUserProperties({
                name: user.name,
            });
        }

        window.heap.addEventProperties({
            'asta.variant': 'autodiscovery',
        });
    }, [scriptLoaded, user]);

    useEffect(() => {
        if (document.getElementById('heap-analytics')) {
            return;
        }
        const script = document.createElement('script');
        script.id = 'heap-analytics';
        script.text = `window.heapReadyCb = window.heapReadyCb || [], window.heap = window.heap || [], heap.load = function (e, t) { window.heap.envId = e, window.heap.clientConfig = t = t || {}, window.heap.clientConfig.shouldFetchServerConfig = !1; var a = document.createElement("script"); a.type = "text/javascript", a.async = !0, a.src = "https://cdn.us.heap-api.com/config/" + e + "/heap_config.js"; var r = document.getElementsByTagName("script")[0]; r.parentNode.insertBefore(a, r); var n = ["init", "startTracking", "stopTracking", "track", "resetIdentity", "identify", "getSessionId", "getUserId", "getIdentity", "addUserProperties", "addEventProperties", "removeEventProperty", "clearEventProperties", "addAccountProperties", "addAdapter", "addTransformer", "addTransformerFn", "onReady", "addPageviewProperties", "removePageviewProperty", "clearPageviewProperties", "trackPageview"], i = function (e) { return function () { var t = Array.prototype.slice.call(arguments, 0); window.heapReadyCb.push({ name: e, fn: function () { heap[e] && heap[e].apply(heap, t) } }) } }; for (var p = 0; p < n.length; p++)heap[n[p]] = i(n[p]) };
      heap.load("${projectId}");
      `;
        document.head.appendChild(script);
        if (window.heap) {
            setScriptLoaded(true);
        }
    }, []);

    return null;
}
