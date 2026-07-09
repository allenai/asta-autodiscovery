import { ATTR_TRACK_NAME, ATTR_TRACK_PROPS, track, TrackProps } from './track';

function collectTrackableAncestors(target: EventTarget | null): Element[] {
    const ancestors: Element[] = [];

    let current = target instanceof Element ? target.closest(`[${ATTR_TRACK_NAME}]`) : null;
    while (current) {
        ancestors.push(current);
        current = current.parentElement?.closest(`[${ATTR_TRACK_NAME}]`) ?? null;
    }

    return ancestors;
}

function readTrackProps(el: Element): TrackProps {
    const raw = el.getAttribute(ATTR_TRACK_PROPS);
    if (!raw) {
        return {};
    }

    try {
        return JSON.parse(raw);
    } catch {
        return {};
    }
}

function handlePointerDown(event: PointerEvent): void {
    const prefix = event.button === 2 ? 'right_click__' : 'click__';

    for (const el of collectTrackableAncestors(event.target)) {
        const name = el.getAttribute(ATTR_TRACK_NAME);
        if (!name) {
            continue;
        }

        track(prefix + name, readTrackProps(el));
    }
}

/**
 * Installs a capture-phase pointerdown listener on `root` that automatically fires a
 * `click__<name>` (or `right_click__<name>` on right-click) Heap event for every ancestor
 * of the clicked element carrying a `data-track-name` attribute (see `mkTrackAttrs` in
 * `track.ts`). Returns a cleanup function to remove the listener.
 */
export function listenForTrackEvents(root: Document | HTMLElement): () => void {
    root.addEventListener('pointerdown', handlePointerDown as EventListener, { capture: true });

    return () => {
        root.removeEventListener('pointerdown', handlePointerDown as EventListener, {
            capture: true,
        });
    };
}
