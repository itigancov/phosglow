// Phosphor: the look of an old CRT monitor.
// Four effects: a soft glow around bright text, dark scanlines,
// darker corners, and a very faint flicker.
// Shadertoy format: iChannel0 is the rendered terminal, iResolution its size,
// iTime the time in seconds.

const float BLOOM_RADIUS   = 6.0;   // glow reach, in physical pixels
const float BLOOM_STRENGTH = 1.1;   // how bright the glow gets
const float BLOOM_CUTOFF   = 0.25;  // only pixels brighter than this glow
const int   SAMPLES        = 24;

const float SCAN_PERIOD = 4.0;      // pixels from one scanline to the next
const float SCAN_DEPTH  = 0.20;     // 0 = no scanlines, 1 = black lines
const float VIGNETTE    = 0.35;     // how dark the corners get
const float FLICKER     = 0.012;    // brightness change over time

float luma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec4 base = texture(iChannel0, uv);

    // Glow: collect light from bright pixels nearby.
    vec3 bloom = vec3(0.0);
    float wsum = 0.0;
    for (int i = 0; i < SAMPLES; i++) {
        float f = float(i) + 0.5;
        float r = sqrt(f / float(SAMPLES)) * BLOOM_RADIUS;  // even spread over a disc
        float a = f * 2.39996323;                           // golden angle
        vec2 off = vec2(cos(a), sin(a)) * r;
        float w = exp(-(r * r) / (BLOOM_RADIUS * BLOOM_RADIUS * 0.35));
        vec3 s = texture(iChannel0, (fragCoord + off) / iResolution.xy).rgb;
        bloom += s * max(luma(s) - BLOOM_CUTOFF, 0.0) * w;
        wsum += w;
    }
    vec3 color = base.rgb + bloom / wsum * BLOOM_STRENGTH;

    // Scanlines: a dark band repeating down the screen.
    float scan = 0.5 + 0.5 * cos(6.2831853 * fragCoord.y / SCAN_PERIOD);
    color *= 1.0 - SCAN_DEPTH * scan;

    // Vignette: the corners get darker.
    vec2 d = uv - 0.5;
    color *= 1.0 - VIGNETTE * dot(d, d) * 2.0;

    // Flicker: a slow, tiny change in brightness.
    color *= 1.0 + FLICKER * sin(iTime * 40.0);

    fragColor = vec4(color, base.a);
}
