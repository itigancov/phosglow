// Phosphor: the look of an old CRT monitor.
// Effects: a soft glow around bright text (extra for the brightest, a little
// for amber), dark scanlines, darker corners, and a pulsing cursor halo.
// Shadertoy format: iChannel0 is the rendered terminal, iResolution its size,
// iTime the time in seconds.

const float BLOOM_RADIUS   = 9.0;   // glow reach, in physical pixels
const float BLOOM_STRENGTH = 1.1;   // how bright the glow gets
const float BLOOM_CUTOFF   = 0.30;  // only pixels brighter than this glow
const int   SAMPLES        = 32;
const float HOT_BOOST      = 2.0;   // extra glow for the brightest green pixels (the mascot)

const float SCAN_PERIOD = 6.0;      // pixels from one scanline to the next
const float SCAN_DEPTH  = 0.25;     // 0 = no scanlines, 1 = black lines
const float VIGNETTE    = 0.50;     // how dark the corners get
const float FLICKER     = 0.0;      // brightness change over time
const vec3  CENTER_LIFT = vec3(0.008, 0.030, 0.010);  // green added to the middle of the screen

const vec3  WARM_GLOW     = vec3(0.96, 0.70, 0.30);  // amber glow colour
const float WARM_STRENGTH = 0.8;    // glow for amber text ("auto mode on")

const float CURSOR_RADIUS = 14.0;   // cursor glow reach, in physical pixels
const float CURSOR_GLOW   = 0.35;   // cursor glow brightness
const float CURSOR_PULSE  = 0.25;   // how much the cursor glow pulses (0 = steady)

float luma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

// Green only, so white and grey text does not get the extra glow.
float greenMask(vec3 c) {
    return smoothstep(0.05, 0.25, c.g - max(c.r, c.b));
}

// Amber only. Red has a low green/red ratio, so it stays unlit.
float warmMask(vec3 c) {
    return smoothstep(0.30, 0.50, c.r - c.b)
         * smoothstep(0.50, 0.65, c.g / max(c.r, 0.001));
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec4 base = texture(iChannel0, uv);

    // Glow: collect light from bright pixels nearby.
    vec3 bloom = vec3(0.0);
    float warm = 0.0;
    float wsum = 0.0;
    for (int i = 0; i < SAMPLES; i++) {
        float f = float(i) + 0.5;
        float r = sqrt(f / float(SAMPLES)) * BLOOM_RADIUS;  // even spread over a disc
        float a = f * 2.39996323;                           // golden angle
        vec2 off = vec2(cos(a), sin(a)) * r;
        float w = exp(-(r * r) / (BLOOM_RADIUS * BLOOM_RADIUS * 0.35));
        vec3 s = texture(iChannel0, (fragCoord + off) / iResolution.xy).rgb;
        bloom += s * max(luma(s) - BLOOM_CUTOFF, 0.0) * (1.0 + HOT_BOOST * smoothstep(0.6, 0.9, luma(s)) * greenMask(s)) * w;
        warm += warmMask(s) * w;
        wsum += w;
    }
    vec3 color = base.rgb + bloom / wsum * BLOOM_STRENGTH
               + WARM_GLOW * (warm / wsum) * WARM_STRENGTH;

    // Cursor: a soft halo that pulses slowly. Only the cursor moves.
    if (iCursorVisible == 1) {
        vec2 c0 = vec2(iCurrentCursor.x, iCurrentCursor.y - iCurrentCursor.w);
        vec2 c1 = vec2(iCurrentCursor.x + iCurrentCursor.z, iCurrentCursor.y);
        vec2 q = max(max(c0 - fragCoord, fragCoord - c1), 0.0);
        float halo = exp(-dot(q, q) / (CURSOR_RADIUS * CURSOR_RADIUS * 0.35));
        float pulse = 1.0 - CURSOR_PULSE * (0.5 + 0.5 * sin(iTime * 2.5));
        color += iCurrentCursorColor.rgb * halo * CURSOR_GLOW * pulse;
    }

    // Scanlines: a dark band repeating down the screen.
    float scan = 0.5 + 0.5 * cos(6.2831853 * fragCoord.y / SCAN_PERIOD);
    color *= 1.0 - SCAN_DEPTH * scan;

    // Centre lift: the middle of the glass is lit, so the vignette has something to darken.
    vec2 d = uv - 0.5;
    color += CENTER_LIFT * (1.0 - smoothstep(0.0, 0.75, length(d)));

    // Vignette: the corners get darker.
    color *= 1.0 - VIGNETTE * dot(d, d) * 2.0;

    // Flicker: a slow, tiny change in brightness.
    color *= 1.0 + FLICKER * sin(iTime * 40.0);

    fragColor = vec4(color, base.a);
}
