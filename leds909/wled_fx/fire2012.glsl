// Fire 2012 (WLED/FastLED port) - heat simulation, one column = one strip
uniform float uCool;
uniform float uSpark;
uniform float uBoost;
uniform float uSpeed;
uniform float uScale;
uniform float uSeed;
uniform float uBass;
uniform float uARSpark;
uniform float uARBoost;
out vec4 fragColor;
float hash(vec2 p){
    p = fract(p*vec2(123.34,456.21));
    p += dot(p, p+45.32);
    return fract(p.x*p.y);
}
void main(){
    vec2 uv = vUV.st;
    const float H = 288.0;
    float SEGLEN = 128.0 * max(0.05, uScale);
    float i = uv.y * SEGLEN;
    float ign = max(3.0, SEGLEN*0.1);
    float heatSelf = texture(sTD2DInputs[0], uv).r * 255.0;
    float coolmax = ((20.0 + uCool/3.0)*16.0)/SEGLEN + 2.0;
    float cool = hash(uv*vec2(911.0,373.0) + uSeed) * coolmax * uSpeed;
    float minTemp = (i < ign) ? (ign - i)/4.0 + 16.0 : 0.0;
    float heat = max(heatSelf - cool, minTemp);
    if (i > 1.5) {
        float h1 = texture(sTD2DInputs[0], uv - vec2(0.0, 1.0/H)).r * 255.0;
        float h2 = texture(sTD2DInputs[0], uv - vec2(0.0, 2.0/H)).r * 255.0;
        heat = (h1 + 2.0*h2) / 3.0;
    }
    float sparkP = clamp(uSpark/255.0 + uARSpark*uBass*0.4, 0.0, 1.0) * uSpeed / max(1.0, ign);
    if (i < ign && hash(uv*vec2(127.0,311.0) + uSeed*1.31) < sparkP) {
        float boost = (17.0 + uBoost + uARBoost*uBass*140.0) * (ign - i*0.5)/ign;
        float lo = 96.0 + 2.0*boost;
        float hi = 207.0 + boost;
        float add = lo + hash(uv*vec2(269.0,183.0) + uSeed*2.17) * (hi - lo);
        heat = min(heat + add, 255.0);
    }
    fragColor = vec4(vec3(heat/255.0), 1.0);
}
