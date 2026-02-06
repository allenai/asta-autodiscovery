import { isNumber } from '@mui/x-data-grid/internals';

import { isBrowser } from '@/runs/utils/env';
import { isBoolean, isString } from '@/runs/utils/typeUtils';

export type HeapPropKey = string | number;
export type HeapPropValue = string | number | boolean | null;
export type HeapPropObject = { [key: HeapPropKey]: HeapPropValue };

export type HeapInstance = {
    addEventProperties: (obj: HeapPropObject) => void;
    addUserProperties: (obj: HeapPropObject) => void;
    appid: string;
    clearEventProperties: () => void;
    config: unknown;
    getIdentity(): string | null;
    getUserId(): string;
    identify(userId: string): void;
    loaded: boolean;
    removeEventProperty: (key: HeapPropKey) => void;
    resetIdentity: never; // DO NOT USE, it'll affect other projects sharing the heap account
    track: (eventName: string, props?: HeapPropObject | null) => void;
};

const HEAP_EVENT_PROP_REGEX = /^[a-zA-Z][\w\s:\-.()]{1,50}$/;

export function optHeap(): HeapInstance | null | undefined {
    const heap = window.heap;

    // If heap analytics are disabled, heap will be undefined
    if (heap === undefined) {
        return;
    }

    if (!isBrowser() || !isHeapInstance(heap)) {
        return null;
    }

    return heap || null;
}

export function runWithHeap(callback: (inst: HeapInstance) => any): void {
    const heap = optHeap();
    if (heap === undefined) {
        return;
    }

    if (heap === null) {
        if (isBrowser()) {
            logOnce(() => console.warn('Attempted to use Heap before the global was set'));
        }
        return;
    }

    try {
        callback(getProxiedHeap(heap));
    } catch (error) {
        console.error('caught error in runWithHeap() callback', error);
    }
}

const NOOP = () => {};

export function getProxiedHeap(heap: HeapInstance): HeapInstance {
    // Wrap addEventProperties to catch potentially bad values being added which have in the past exploded
    // our redshift
    return new Proxy(heap, {
        get: (target, prop: keyof HeapInstance) => {
            switch (prop) {
                // These methods are not allowed to be called, as they could break other projects sharing the heap account
                case 'resetIdentity':
                    return NOOP;

                case 'addEventProperties':
                    return (heapProps: Record<string, any>) => {
                        // iterate over the prop keys and filter out and error on any bad keys
                        const cleanedProperties: any = Object.keys(heapProps)
                            .filter((key) => isHeapPropKeyValid(key))
                            .reduce(
                                (obj, key) => {
                                    obj[key] = heapProps[key];
                                    return obj;
                                },
                                {} as Record<string, any>
                            );

                        // If there are any keys left, call the original heap method
                        if (Object.keys(cleanedProperties).length) {
                            return target[prop](cleanedProperties);
                        }
                    };

                default:
                    return target[prop];
            }
        },
    });
}

export function isHeapPropKeyValid(key: any): boolean {
    return isString(key) && HEAP_EVENT_PROP_REGEX.test(key);
}

/**
 * This validates the shape of our HeapInstance to ensure it matches
 * the expected interface at runtime. Due to interventions by browser-
 * and network-level ad-blockers, relying on window.heap being defined
 * does not guarantee all functions are present.
 */
function isHeapInstance(heap: any): heap is HeapInstance {
    return (
        !!heap &&
        typeof heap.clearEventProperties === 'function' &&
        typeof heap.identify === 'function' &&
        typeof heap.resetIdentity === 'function' &&
        typeof heap.track === 'function'
    );
}

let hasLogged = false;
function logOnce(cb: () => void): void {
    if (hasLogged) {
        return;
    }
    hasLogged = true;
    cb();
}

// Removes values from event data that cannot be sent to Heap
export function getHeapPropsFromEventData(eventData: Record<HeapPropKey, unknown>): HeapPropObject {
    const heapProps: HeapPropObject = {};
    for (const [key, value] of Object.entries(eventData)) {
        if (isString(value) || isNumber(value) || isBoolean(value)) {
            heapProps[key] = value;
        } else {
            console.warn(
                `event prop "${key}" was dropped because "${typeof value}" is not a valid Heap prop type`
            );
        }
    }
    return heapProps;
}
