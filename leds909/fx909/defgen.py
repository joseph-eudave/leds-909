import json

PREAMBLE = '''#define TAU 6.28318530718
float c01(float t){ return clamp(t,0.0,1.0); }
float suave(float t){ float c=c01(t); return c*c*(3.0-2.0*c); }
float frac(float t){ return t-floor(t); }
float azar(float n){
    uint h = uint(n + 1000000.0);
    h ^= 0x9e3779b9u; h *= 0x85ebca6bu; h ^= h >> 13; h *= 0xc2b2ae35u; h ^= h >> 16;
    return float(h) / 4294967296.0;
}
'''

PROGS = []

PROGS.append(dict(id='fuego', name='Fuego', colA=(1.0,0.35,0.05), colB=(0.55,0.02,0.0),
 params=[('viveza','Viveza',1.2,0.3,2.5),('altura','Altura',0.55,0.2,1.0),('fondo','Fondo',0.04,0.0,0.4)],
 body='''float sube = uFxTime*uViveza;
float h = t.y;
float cx = t.x*9.0; float cy = h*6.0 - sube;
float ix=floor(cx), iy=floor(cy);
float fx=suave(cx-ix), fy=suave(cy-iy);
float n00=azar(ix*7919.0+iy*104729.0), n10=azar((ix+1.0)*7919.0+iy*104729.0);
float n01=azar(ix*7919.0+(iy+1.0)*104729.0), n11=azar((ix+1.0)*7919.0+(iy+1.0)*104729.0);
float ruido = mix(mix(n00,n10,fx), mix(n01,n11,fx), fy);
float calor = c01((1.0 - h/uAltura) + (ruido-0.5)*0.9);
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA,calor)*(suelo+rango*calor);'''))

PROGS.append(dict(id='aurora', name='Aurora', colA=(0.1,0.9,0.6), colB=(0.05,0.15,0.5),
 params=[('velocidad','Velocidad',0.75,0.1,2.0),('bandas','Bandas',3,1,5),('ondulacion','Ondulacion',0.6,0.0,1.0),('fondo','Fondo',0.1,0.0,0.5)],
 body='''float tc = compases*uVelocidad;
float h = t.y + uOndulacion*0.15*sin(TAU*(t.x*1.5 + tc*0.5));
float k = 0.5+0.5*sin(TAU*(h*uBandas - tc)); k*=k;
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='plasma', name='Plasma', colA=(0.2,0.5,1.0), colB=(0.9,0.15,0.35),
 params=[('velocidad','Velocidad',1.0,0.1,3.0),('escala','Escala',1.5,0.5,4.0),('complejidad','Complejidad',3,1,4),('fondo','Fondo',0.05,0.0,0.5)],
 body='''float tc = TAU*compases*uVelocidad; float e = uEscala*TAU;
float s = sin(t.x*e + tc);
if (uComplejidad>1.5) s += sin(t.y*e*0.8 - tc*1.3);
if (uComplejidad>2.5) s += sin((t.x+t.y)*e*0.6 + tc*0.7);
if (uComplejidad>3.5) s += sin(length(t-0.5)*e*2.0 - tc);
float k = 0.5+0.5*s/uComplejidad;
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='espiral', name='Espiral', colA=(1.0,0.75,0.1), colB=(0.35,0.05,0.55),
 params=[('brazos','Brazos',2,1,4),('vueltas','Vueltas',1.0,0.25,3.0),('torsion','Torsion',1,0,3),('ancho','Ancho',0.4,0.1,0.9),('fondo','Fondo',0.06,0.0,0.5)],
 body='''float ang = atan(t.y-0.5, t.x-0.5)/TAU+0.5;
float f = frac(uBrazos*(ang - compases*uVueltas) + uTorsion*t.x);
float d = (f<0.5? f : 1.0-f)*2.0;
float k = suave(1.0 - d/uAncho);
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='tunel', name='Tunel', colA=(0.1,1.0,0.8), colB=(0.0,0.2,0.5),
 params=[('anillos','Anillos',0.5,0.25,2.0),('grosor','Grosor',0.2,0.08,0.5),('sentido','Sentido',0,0,1),('fondo','Fondo',0.05,0.0,0.5)],
 body='''float pos = -uGrosor + frac(pulsos*uAnillos)*(1.0+2.0*uGrosor);
float s = t.y; if (uSentido>0.5) s = 1.0-t.y;
float d = abs(s-pos);
float cabeza = uGrosor*0.5;
float k = d<=cabeza? 1.0 : (d<uGrosor? pow(1.0-(d-cabeza)/(uGrosor-cabeza),2.0) : 0.0);
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='marea', name='Marea', colA=(0.15,0.85,1.0), colB=(0.05,0.3,0.7),
 params=[('velocidad','Velocidad',1.0,0.25,3.0),('ancho','Ancho',0.3,0.1,0.6),('fondo','Fondo',0.04,0.0,0.4)],
 body='''float fase = frac(compases*uVelocidad);
bool ida = fase<0.5;
float tt = ida? fase*2.0 : 2.0-fase*2.0;
float pos = -uAncho + tt*(1.0+2.0*uAncho);
float d = abs((1.0-t.y)-pos)/uAncho;
float k = d<1.0? 0.5+0.5*cos(3.14159*d) : 0.0;
float suelo=uFondo; float rango=1.0-suelo;
float g = suelo+rango*k;
col = ida? uColA*g + uColB*suelo : uColA*suelo + uColB*g;'''))

PROGS.append(dict(id='titileo', name='Titileo', colA=(1.0,0.95,0.75), colB=(0.1,0.1,0.25),
 params=[('velocidad','Velocidad',0.8,0.2,2.5),('densidad','Densidad',0.5,0.1,1.0),('fondo','Fondo',0.05,0.0,0.4)],
 body='''float cu = floor(t.x*16.0), cv = floor(t.y*4.0);
float c = cv*64.0+cu;
float k=0.0;
if (azar(c)<uDensidad){
    float f = uVelocidad*(0.4+0.6*azar(c+7.0));
    float base = 0.5-0.5*cos(TAU*(f*uFxTime+azar(c+13.0)));
    float dentro = frac(t.x*16.0);
    float mes = suave(dentro/0.2)*suave((1.0-dentro)/0.2);
    k = base*base*base*mes;
}
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='brasa', name='Brasa', colA=(1.0,0.45,0.15), colB=(0.4,0.05,0.0),
 params=[('deriva','Deriva',0.6,0.0,1.5),('fondo','Fondo',0.18,0.0,0.6)],
 body='''float f = frac(uBarPhase - t.x*uDeriva);
float tri = f<0.5? f*2.0 : (1.0-f)*2.0;
float suelo=uFondo; float rango=1.0-suelo;
float k = suelo + rango*suave(tri);
col = mix(uColB,uColA, k);'''))

PROGS.append(dict(id='corazon', name='Corazon', colA=(1.0,0.2,0.25), colB=(0.6,0.05,0.5),
 params=[('retraso','Retraso',0.35,0.2,0.55),('caida','Caida',6,2,12),('onda','Onda',0.6,0.0,1.0),('fondo','Fondo',0.0,0.0,0.4)],
 body='''float ph = fract(pulsos);
float lub = exp(-uCaida*ph);
float llega = uRetraso + uOnda*0.25*(1.0-t.y);
float dub = ph>=llega? exp(-uCaida*(ph-llega)) : 0.0;
float suelo=uFondo; float rango=1.0-suelo;
col = uColA*(suelo+rango*lub) + uColB*(suelo+rango*dub);'''))

PROGS.append(dict(id='vortice', name='Vortice', colA=(0.2,1.0,0.4), colB=(0.5,0.1,0.9),
 params=[('brazos','Brazos',1,1,3),('vueltas','Vueltas',1,0.25,2.0),('torsion','Torsion',2,0.5,4),('estela','Estela',0.35,0.1,0.7),('fondo','Fondo',0.05,0.0,0.5)],
 body='''float ang = atan(t.y-0.5, t.x-0.5)/TAU+0.5;
float f = frac(uBrazos*(compases*uVueltas - ang) - uTorsion*t.y*t.y);
float cabeza = uEstela*0.5;
float k = f<=cabeza? 1.0 : (f<uEstela? pow(1.0-(f-cabeza)/(uEstela-cabeza),2.0) : 0.0);
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='flujo', name='Flujo', colA=(0.1,0.85,0.8), colB=(0.55,0.1,0.75),
 params=[('velocidad','Velocidad',0.6,0.05,2.0),('escala','Escala',1.6,0.5,4.0),('turbulencia','Turbulencia',1,0,2),('contraste','Contraste',0.6,0.0,1.0),('fondo','Fondo',0.03,0.0,0.5)],
 body='''float tc = TAU*compases*uVelocidad;
float e = uEscala*TAU;
float turb = 2.2*uTurbulencia;
float ax=t.x*e, ay=t.y*e*0.8;
float q1 = sin(ax*0.9 + tc*0.7 + 1.3*sin(ax*1.1 - tc*0.45));
float q2 = sin(ax*0.8 - tc*0.55 + 1.2*sin(ax*1.2 + ay + tc*0.33));
float onda = 0.6*sin(ax + turb*q1 + tc) + 0.4*sin(ax*1.3 + turb*q2 - tc*0.8 + ay);
float k = c01(0.5+0.5*onda);
float g = k + (suave(suave(k))-k)*uContraste;
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*g);'''))

PROGS.append(dict(id='caleidoscopio', name='Caleidoscopio', colA=(1.0,0.85,0.2), colB=(0.75,0.15,0.9),
 params=[('velocidad','Velocidad',1.2,0.1,3.0),('segmentos','Segmentos',6,3,8),('complejidad','Complejidad',2,1,4),('fondo','Fondo',0.08,0.0,0.5)],
 body='''float ang = atan(t.y-0.5, t.x-0.5)/TAU+0.5;
float m = frac(ang*uSegmentos);
float espejo = m<0.5? m*2.0 : (1.0-m)*2.0;
float radio = length(t-0.5)*2.0;
float k = 0.5+0.5*cos(TAU*(espejo*uComplejidad + radio + t.x - compases*uVelocidad));
k*=k;
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='goteo', name='Goteo', colA=(0.3,0.8,1.0), colB=(0.1,0.4,0.9),
 params=[('cada','Cada',2,1,4),('tamano','Tamano',0.12,0.05,0.3),('fondo','Fondo',0.03,0.0,0.4)],
 body='''float f = frac(pulsos/uCada);
bool cayendo = f<0.7;
float pos = cayendo? 1.0+uTam-(f/0.7)*(1.0+uTam) : -1.0;
float salpica = cayendo? 0.0 : exp(-5.0*(f-0.7)/0.3);
float d = (t.y - pos)/uTam;
float ka = (cayendo && d>-0.3 && d<1.0)? (d<0.0? 1.0+d/0.3 : 1.0-d) : 0.0;
float kb = t.y<0.15? salpica*(1.0-t.y/0.15) : 0.0;
float suelo=uFondo; float rango=1.0-suelo;
col = uColA*(suelo+rango*ka) + uColB*(suelo+rango*kb);'''))

PROGS.append(dict(id='barrido', name='Barrido', colA=(1.0,0.9,0.5), colB=(0.2,0.25,0.4),
 params=[('ancho','Ancho',0.18,0.05,0.6),('fondo','Fondo',0.05,0.0,0.4)],
 body='''float d = abs(t.x-uBarPhase); if (d>0.5) d=1.0-d;
float brillo = d<uAncho? 1.0-d/uAncho : 0.0;
float mezcla = brillo*(1.0-uFondo)+uFondo;
col = mix(uColB,uColA, mezcla);'''))

PROGS.append(dict(id='corte', name='Corte', colA=(1.0,1.0,1.0), colB=(0.85,0.1,0.15),
 params=[('division','Division',0,0,2),('estela','Estela',0.3,0.05,0.9),('fondo','Fondo',0.06,0.0,0.5)],
 body='''float ciclos = uDivision<0.5? 1.0 : (uDivision<1.5? 2.0 : 4.0);
float fase = frac(uBarPhase*ciclos);
float d = frac(fase - t.x);
float golpe = d<uEstela? 1.0-d/uEstela : 0.0;
col = mix(uColB,uColA, uFondo+(1.0-uFondo)*golpe);'''))

PROGS.append(dict(id='rebote', name='Rebote', colA=(1.0,0.6,0.1), colB=(0.1,0.5,1.0),
 params=[('division','Division',0,0,2),('caida','Caida',5,2,12),('fondo','Fondo',0.04,0.0,0.4)],
 body='''float tiempos = uDivision<0.5? 1.0 : (uDivision<1.5? 2.0 : 4.0);
float golpes = pulsos/tiempos;
float g0 = floor(golpes); float fase = golbes_golpes(f, g0);
col = vec3(0.0);'''))

PROGS.append(dict(id='estallido', name='Estallido', colA=(1.0,0.95,0.85), colB=(1.0,0.3,0.1),
 params=[('modo','Modo',0,0,1),('cada','Cada',2,1,4),('ancho','Ancho',0.15,0.05,0.4),('fondo','Fondo',0.04,0.0,0.4)],
 body='''float r = length(t-0.5)/1.2247;
float f = frac(pulsos/uCada);
float radio = f*(1.0+uAncho); float k=0.0;
if (uModo>0.5){
    float fc = frac(compases);
    if (fc<0.75) radio = (1.0-fc/0.75)*(1.0+uAncho);
    else { radio=-1.0; k=exp(-6.0*(fc-0.75)/0.25); }
}
if (radio>=0.0){ float d=abs(r-radio)/uAncho; if (d<1.0) k=1.0-d*d; }
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

PROGS.append(dict(id='lluvia', name='Lluvia', colA=(0.55,0.85,1.0), colB=(0.1,0.25,0.5),
 params=[('velocidad','Velocidad',0.8,0.3,2.0),('densidad','Densidad',0.6,0.1,1.0),('estela','Estela',0.35,0.1,0.8),('sentido','Sentido',0,0,1),('fondo','Fondo',0.04,0.0,0.4)],
 body='''float id = floor(t.x*12.0);
float k=0.0;
if (azar(id)<uDensidad){
    float ritmo = uVelocidad*(0.6+0.6*azar(id+3.0));
    float cabezaEn = frac(uFxTime*ritmo + azar(id+5.0))*(1.0+uEstela);
    float s = t.y; if (uSentido>0.5) s = 1.0-t.y;
    float d = cabezaEn - s;
    float cabeza = uEstela*0.5;
    k = (d>=0.0 && d<=cabeza)? 1.0 : ((d>cabeza && d<uEstela)? pow(1.0-(d-cabeza)/(uEstela-cabeza),2.0) : 0.0);
}
float suelo=uFondo; float rango=1.0-suelo;
col = mix(uColB,uColA, suelo+rango*k);'''))

# fix rebote body (placeholder above was corrupted during drafting)
PROGS[[p['id'] for p in PROGS].index('rebote')]['body'] = '''float tiempos = uDivision<0.5? 1.0 : (uDivision<1.5? 2.0 : 4.0);
float golpes = pulsos/tiempos;
float g0 = floor(golpes); float fase = golpes-g0;
float env = exp(-uCaida*fase);
bool izq = mod(g0,2.0)<0.5;
float suelo=uFondo; float rango=1.0-suelo;
col = t.x<0.5? uColA*(suelo+rango*(izq?env:0.0)) : uColB*(suelo+rango*(izq?0.0:env));'''


def shader_for(p):
    if not any(x[0]=='arlevel' for x in p['params']):
        p['params'] = p['params'] + [('arlevel','Audio React',0.0,0.0,1.0)]
    unis = ''.join('uniform float u%s;\n' % n.capitalize() for n, _, _, _, _ in p['params'])
    unis += 'uniform vec3 uColA;\nuniform vec3 uColB;\nuniform float uFxTime; uniform float uPulsosS;\nuniform float uBeat;\nuniform float uBeatPhase;\nuniform float uBpm;\nuniform float uBass;\nuniform float uMid;\nuniform float uHigh;\nuniform float uRvel;\n'
    main = ('void main(){\n    vec2 t = vUV.st;\n'
            '    float pulsos = uPulsosS;\n'
            '    float compases = pulsos/4.0;\n'
            '    float uBarPhase = fract(compases);\n'
            '    vec3 col = vec3(0.0);\n' + p['body'] +
            '\n    col *= clamp(1.0 + uArlevel*(uBass*1.1 + uRvel*0.9 - 0.18), 0.0, 2.0);\n'
            '    fragColor = vec4(col, 1.0);\n}\n')
    return 'out vec4 fragColor;\n' + PREAMBLE + unis + main


out = dict(progs=[dict(id=p['id'], name=p['name'], colA=list(p['colA']), colB=list(p['colB']),
                       params=[list(x) for x in p['params']] + [['arlevel', 'Audio React', 0.0, 0.0, 1.0]],
                       glsl=shader_for(p)) for p in PROGS])
json.dump(out, open('C:\\Users\\josep\\OneDrive\\Escritorio\\leds 909\\leds909\\fx909\\programs.json', 'w'))
print('programs:', len(PROGS))
