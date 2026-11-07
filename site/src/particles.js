import * as THREE from 'three';
import { GPUComputationRenderer } from 'three/examples/jsm/misc/GPUComputationRenderer.js';

// GPGPU particles: positions live in a float texture, updated in a fragment shader every frame.
// Each particle is pulled toward a blend of two target shapes (A -> B), pushed by curl noise and the mouse.

const NOISE = /* glsl */ `
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x,289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+2.0*C.xxx; vec3 x3=x0-1.0+3.0*C.xxx;
  i=mod(i,289.0);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=1.0/7.0; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
vec3 snoiseVec3(vec3 x){
  return vec3(snoise(x), snoise(vec3(x.y-19.1,x.z+33.4,x.x+47.2)), snoise(vec3(x.z+74.2,x.x-124.5,x.y+99.4)));
}
vec3 curl(vec3 p){
  const float e=0.1; vec3 dx=vec3(e,0,0), dy=vec3(0,e,0), dz=vec3(0,0,e);
  vec3 px0=snoiseVec3(p-dx), px1=snoiseVec3(p+dx), py0=snoiseVec3(p-dy), py1=snoiseVec3(p+dy), pz0=snoiseVec3(p-dz), pz1=snoiseVec3(p+dz);
  float x=py1.z-py0.z-pz1.y+pz0.y; float y=pz1.x-pz0.x-px1.z+px0.z; float z=px1.y-px0.y-py1.x+py0.x;
  return normalize(vec3(x,y,z)/(2.0*e));
}`;

const SIM = /* glsl */ `
uniform sampler2D tA; uniform sampler2D tB;
uniform vec3 uShiftA; uniform vec3 uShiftB;
uniform float uBlend; uniform float uTime; uniform float uDt; uniform float uTurb; uniform float uKick;
uniform vec3 uMouse; uniform float uMouseStr;
${NOISE}
void main(){
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 p = texture2D(texturePosition, uv);
  vec4 a = texture2D(tA, uv); vec4 b = texture2D(tB, uv);
  float rnd = a.w;
  float k = smoothstep(rnd*0.45, rnd*0.45+0.55, uBlend);
  vec3 target = mix(a.xyz + uShiftA, b.xyz + uShiftB, k);
  float travel = k*(1.0-k)*4.0;                       // 1 mid-transition
  vec3 pos = p.xyz;
  float turb = uTurb + travel*2.6 + uKick;
  pos += curl(pos*0.28 + vec3(0.0, uTime*0.06, rnd)) * turb * uDt;
  vec3 d = pos - uMouse; float dl = length(d);
  pos += (d/(dl+1e-4)) * uMouseStr * exp(-dl*dl*0.9) * uDt * 6.0;
  float pull = 1.0 - exp(-uDt*(1.6 + rnd*2.6) * (1.0 - travel*0.6));
  pos = mix(pos, target, pull);
  gl_FragColor = vec4(pos, 1.0);
}`;

const VERT = /* glsl */ `
uniform sampler2D tPos; uniform sampler2D cA; uniform sampler2D cB;
uniform float uBlend; uniform float uSize; uniform float uTime;
attribute vec2 ref; attribute float aRnd;
varying vec3 vCol; varying float vAlpha;
void main(){
  vec3 p = texture2D(tPos, ref).xyz;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float k = smoothstep(aRnd*0.45, aRnd*0.45+0.55, uBlend);
  vCol = mix(texture2D(cA, ref).rgb, texture2D(cB, ref).rgb, k);
  float tw = 0.6 + 0.4*sin(uTime*1.7 + aRnd*60.0);
  vAlpha = tw;
  gl_PointSize = uSize * (0.45 + aRnd*0.9) / -mv.z;
}`;

const FRAG = /* glsl */ `
varying vec3 vCol; varying float vAlpha;
uniform float uOpacity;
void main(){
  vec2 c = gl_PointCoord - 0.5; float d = length(c);
  if (d > 0.5) discard;
  float a = smoothstep(0.5, 0.0, d); a *= a;
  gl_FragColor = vec4(vCol * (0.75 + a*0.6), a * vAlpha * uOpacity);
}`;

export class Particles {
  constructor(renderer, size) {
    this.size = size;
    this.count = size * size;
    this.renderer = renderer;

    this.rnd = new Float32Array(this.count);
    for (let i = 0; i < this.count; i++) this.rnd[i] = Math.random();

    const gpu = new GPUComputationRenderer(size, size, renderer);
    if (!renderer.extensions.has('EXT_color_buffer_float')) gpu.setDataType(THREE.HalfFloatType);
    this.gpu = gpu;

    // Start: a large scattered cloud so the first frames "assemble" the hero.
    const init = gpu.createTexture();
    const d = init.image.data;
    for (let i = 0; i < this.count; i++) {
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1), r = 9 + Math.random() * 14;
      d[i * 4] = r * Math.sin(ph) * Math.cos(th);
      d[i * 4 + 1] = r * Math.cos(ph);
      d[i * 4 + 2] = r * Math.sin(ph) * Math.sin(th) - 6;
      d[i * 4 + 3] = 1;
    }
    this.posVar = gpu.addVariable('texturePosition', SIM, init);
    gpu.setVariableDependencies(this.posVar, [this.posVar]);
    const u = this.posVar.material.uniforms;
    Object.assign(u, {
      tA: { value: null }, tB: { value: null },
      uShiftA: { value: new THREE.Vector3() }, uShiftB: { value: new THREE.Vector3() },
      uBlend: { value: 0 }, uTime: { value: 0 }, uDt: { value: 0.016 }, uTurb: { value: 0.35 }, uKick: { value: 0 },
      uMouse: { value: new THREE.Vector3(999, 999, 999) }, uMouseStr: { value: 0 },
    });
    const err = gpu.init();
    if (err) throw new Error(err);
    this.simU = u;

    const geo = new THREE.BufferGeometry();
    const ref = new Float32Array(this.count * 2);
    for (let i = 0; i < this.count; i++) {
      ref[i * 2] = ((i % size) + 0.5) / size;
      ref[i * 2 + 1] = (Math.floor(i / size) + 0.5) / size;
    }
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.count * 3), 3));
    geo.setAttribute('ref', new THREE.BufferAttribute(ref, 2));
    geo.setAttribute('aRnd', new THREE.BufferAttribute(this.rnd, 1));

    this.material = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG,
      uniforms: {
        tPos: { value: null }, cA: { value: null }, cB: { value: null },
        uBlend: { value: 0 }, uSize: { value: 30 }, uTime: { value: 0 }, uOpacity: { value: 1 },
      },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
    this.points = new THREE.Points(geo, this.material);
    this.points.frustumCulled = false;

    this.posTex = [];
    this.colTex = [];
  }

  // shapes: [{pos, colors}] from buildShapes. Reuses the textures on resize.
  setShapes(shapes) {
    shapes.forEach((s, i) => {
      if (!this.posTex[i]) {
        this.posTex[i] = new THREE.DataTexture(s.pos, this.size, this.size, THREE.RGBAFormat, THREE.FloatType);
        this.colTex[i] = new THREE.DataTexture(s.colors, this.size, this.size, THREE.RGBAFormat, THREE.FloatType);
      } else {
        this.posTex[i].image.data = s.pos;
        this.colTex[i].image.data = s.colors;
      }
      this.posTex[i].needsUpdate = true;
      this.colTex[i].needsUpdate = true;
    });
  }

  setState(a, b, blend, shiftA, shiftB) {
    const u = this.simU, m = this.material.uniforms;
    u.tA.value = this.posTex[a]; u.tB.value = this.posTex[b];
    u.uBlend.value = blend; m.uBlend.value = blend;
    u.uShiftA.value.copy(shiftA); u.uShiftB.value.copy(shiftB);
    m.cA.value = this.colTex[a]; m.cB.value = this.colTex[b];
  }

  update(t, dt) {
    this.simU.uTime.value = t;
    this.simU.uDt.value = Math.min(dt, 1 / 30);
    this.material.uniforms.uTime.value = t;
    this.gpu.compute();
    this.material.uniforms.tPos.value = this.gpu.getCurrentRenderTarget(this.posVar).texture;
  }
}
