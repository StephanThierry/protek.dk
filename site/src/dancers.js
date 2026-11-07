// Claude, OpenAI and Gemini dancing in 3D: the animated GLB made in Blender for protek.dk/blender
// (designs/blender/blender/scene.py -> export_dancers_glb). The SVG dancers stay as the fallback.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

export function initDancers() {
  const box = document.querySelector('.dancers');
  if (!box) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const start = () => {
    const canvas = document.createElement('canvas');
    canvas.className = 'dancers__3d';
    canvas.setAttribute('aria-hidden', 'true');
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    } catch (e) {
      return; // keep the SVG dancers
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.toneMapping = THREE.NeutralToneMapping; // keeps the brand colours true
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.35;
    const key = new THREE.DirectionalLight(0xfff4e8, 2.4);
    key.position.set(-3, 4, 6);
    const rim = new THREE.DirectionalLight(0x9fddf7, 1.6);
    rim.position.set(4, 2, -5);
    scene.add(key, rim);
    const camera = new THREE.PerspectiveCamera(30, 2.5, 0.1, 100);

    let mixer = null;
    new GLTFLoader().load('models/dancers.glb', (gltf) => {
      scene.add(gltf.scene);
      mixer = new THREE.AnimationMixer(gltf.scene);
      gltf.animations.forEach((clip) => mixer.clipAction(clip).play());
      if (reduced) mixer.setTime(9 / 24); // a still pose, no dancing
      box.appendChild(canvas);
      box.classList.add('is-3d');
      resize();
    }, undefined, (e) => console.warn('dancers.glb failed to load, keeping the SVG dancers:', e));

    function resize() {
      const r = canvas.getBoundingClientRect();
      if (!r.width) return;
      renderer.setSize(r.width, r.height, false);
      camera.aspect = r.width / r.height;
      // all three in frame: 8.5 units away at 2.5:1, further back on narrower boxes
      const z = camera.aspect < 2.5 ? 8.5 * 2.5 / camera.aspect : 8.5;
      camera.position.set(0, 0.5, z);
      camera.lookAt(0, 0.2, 0);
      camera.updateProjectionMatrix();
    }
    new ResizeObserver(resize).observe(box);

    let visible = true;
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(box);
    const clock = new THREE.Clock();
    (function frame() {
      requestAnimationFrame(frame);
      const dt = clock.getDelta();
      if (!visible || !mixer) return;
      if (!reduced) mixer.update(dt);
      renderer.render(scene, camera);
    })();
  };

  // Only create the extra WebGL context when the block comes close.
  new IntersectionObserver(([en], obs) => {
    if (en.isIntersecting) { obs.disconnect(); start(); }
  }, { rootMargin: '400px 0px' }).observe(box);
}
