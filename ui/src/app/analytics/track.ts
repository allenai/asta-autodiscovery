export const ATTR_TRACK_NAME = 'data-track-name' as const;
export const ATTR_TRACK_PROPS = 'data-track-props' as const;

export type TrackName = string;
export type TrackProp = string | number | boolean;
export type TrackProps = Record<string, TrackProp | Record<string, TrackProp>>; // Max 2 levels deep

// HTML attributes for tracking data
export type TrackHTMLAttrs<TTrackName> = {
    [ATTR_TRACK_NAME]: TTrackName;
    [ATTR_TRACK_PROPS]?: string;
};

/**
 * Add attributes to element for tracking
 *
 * NOTE: Use the mk*TrackAttrs functions in the respective prop file, not this function directly
 *
 * Example: <div {...mkTrackAttrs('featured_content_item', {type: 'video'})} />
 * Output: <div data-track-name="featured_content_item" data-track-props="{&quot;type&quot;:&quot;video&quot;}" />
 */
export function mkTrackAttrs<TTrackName extends TrackName>(
    name: TTrackName,
    props: TrackProps = {}
): TrackHTMLAttrs<TTrackName> {
    const attrs: TrackHTMLAttrs<TTrackName> = {
        [ATTR_TRACK_NAME]: name,
    };
    if (Object.keys(props).length > 0) {
        attrs[ATTR_TRACK_PROPS] = JSON.stringify(props);
    }
    return attrs;
}
