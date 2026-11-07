# How the 3D elements of protek.dk/designs/blender were made

This document records the whole process behind the Blender design: the toolchain, every step from the first
script to the live page, the file formats in and out, how each result was checked, and the alternatives that were
considered along the way with the reason each was or was not chosen.

The short version: **Claude Code drives Blender 5.2 through the Blender MCP server**. Every element is built by
Python code in [`blender/scene.py`](blender/scene.py), rendered in Cycles as a fallback image, exported as a
GLB, and shown live and rotating in the browser with Three.js. The one exception is the head of the marble
bust, which is generated from a portrait photo with **TRELLIS** and then finished in Blender by the same script.
The animated star is the hero; the bust turns on its plinth next to the contact heading.

---

## 1. Goals and constraints

- A sixth design for protek.dk where 3D is the theme. It reuses the content of the other designs (CV, GitHub,
  interests, contact) and adds a section on 3D printing with the Blender + Claude Code workflow.
- The Protek star from the Plakat design is the main element. Every section gets a 3D counterpart of the
  particle shapes on the front page (star, helix, GitHub star, knot, prism, contact element).
- Everything must be reproducible from code in the repo and run locally on the owner's machine.
- Rules of the repo: visible text in Danish, code, comments and docs in English. Infrastructure values stay out
  of git (`deploy.config.psd1`).

## 2. Toolchain

| Part | What | Version | License | Role |
| --- | --- | --- | --- | --- |
| GPU | NVIDIA GeForce RTX 5080, 16 GB | driver 616.56 | n/a | Cycles (OptiX), TRELLIS (CUDA) |
| 3D | Blender | 5.2.0 LTS | GPL | modelling, materials, Cycles renders, glTF export |
| Bridge | Blender MCP server (Blender Lab extension `lab_blender_org/mcp`) | for Blender 5.2 | n/a | lets Claude Code run Python in the open Blender session |
| Agent | Claude Code | n/a | n/a | writes and runs `scene.py`, reviews renders, builds the page |
| Web | Three.js | ^0.187 | MIT | live GLBs, AnimationMixer, clipping, custom shaders |
| Web | Vite | ^6.4 | MIT | build with relative base `./` |
| Decoder | three/examples MeshoptDecoder | with Three.js | MIT | decodes EXT_meshopt_compression GLBs |
| Image-to-3D | TRELLIS (`microsoft/TRELLIS`, commit 193e050) | weights `microsoft/TRELLIS-image-large` | MIT (code and weights) | head of the bust |
| Its parts | DINOv2 (image features), FlexiCubes (mesh extraction) | | Apache 2.0 | used inside TRELLIS |
| Its runtime | Python 3.12 venv, PyTorch 2.7.1+cu128, xformers 0.0.31.post1, spconv-cu126 2.3.8 | | BSD / Apache | sm_120 (Blackwell) support |
| Cutout | rembg (u2net) | | MIT / Apache | background removal of the portrait |
| QA | puppeteer-core + Chrome, Pillow | | Apache / MIT-CMU | screenshots, contact sheets |

Every Blender call went through the MCP tool `execute_blender_code`. The script is the source of truth:
the session always ran `exec(open('designs/blender/blender/scene.py').read())` and then a builder function,
so no state lives only inside a `.blend` file.

## 3. Pipeline at a glance

```
SVG coordinates, analytic shapes, portrait photo
        |                                    (TRELLIS: photo -> latent -> PLY, outside the repo)
        v                                                     |
 scene.py in Blender 5.2 (via MCP)  <------------------------ +
   build_*()        -> collections, one per element
   render_one()     -> public/renders/*.webp   (Cycles, OptiX, transparent, fallback images)
   export_*_glb()   -> public/models/*.glb     (glTF 2.0 binary, meshopt)
   check_print()    -> printability numbers quoted on the page
        |
        v
 index.html + src/main.js (hero) + src/views.js (all other elements)
   Three.js renders the GLBs live; the WEBP renders are the no-WebGL fallback
        |
        v
 build.ps1 -> dist/designs/blender  ->  deploy.ps1 -> web server
```

## 4. Step by step

### 4.1 Research

Before building, a web search checked whether Blender MCP was already used heavily for web design. It found
tutorials, a Codrops article on Blender to Three.js workflows, and single portfolio experiments, but no
established showcase. That made a site built this way a useful example in its own right.

### 4.2 Scene setup (`setup_render`, `lights`, `camera`)

- Cycles on the GPU with OptiX, OptiX denoiser, AgX view transform with the Medium High Contrast look.
- Transparent film, so every render can sit on the page background.
- A dark world with a faint teal horizon that only shows in reflections, plus four area lights (warm key,
  cool rim, mint fill, soft top). These match the page palette.
- Output format WEBP RGBA at quality 84, straight from Blender (no conversion step).

### 4.3 The Protek star (`build_star`, `star_shards`, `offset_poly`, `prism_from_poly`)

- **Input:** the nine polygons of the SVG logo used in the Plakat design (viewBox 1000, centre 520,490), the
  same coordinates the particle front page uses, plus the three petrol-blue tones of the logo.
- **Geometry:** each shard is offset outward by half the SVG stroke width (11 units) to match the drawn
  logo, then extruded with a **flat back** and a top that rises toward the tips:
  `z_top = 0.16 + 0.11 * distance_from_centre`. That gives a faceted relief that is also printable.
- **Finish:** bevel modifier (3 segments) with hardened normals, lacquered material (clearcoat 1.0), two thin
  glowing rings at the logo's radii (470 and 330 SVG units).
- **Iterations:**
  - The rings first did not show. Blender primitives are created at the 3D cursor, which sat at (-57, 75).
    Fixed by passing `location=(0, 0, 0)`.
  - Later the rings were tilted 8 and -6 degrees for depth. The owner wanted them flush with the logo, so they
    now lie in the logo plane at z 0.12 and cross the shards like the rings in the SVG.
  - In the live version the overlapping shards z-fought (shimmer) and the white core sphere did not fit. The
    GLB now uses `union_star()`: an exact boolean union of all shards into one closed mesh, without the core,
    exported with flat facets. Smooth shading had blended neighbouring shard tops into smudged highlights.

### 4.4 The other elements

| Element | Builder | How it is made | Live animation (`views.js`) |
| --- | --- | --- | --- |
| Career helix | `build_helix` | two curve tubes along X, 22 rungs, 10 emissive nodes (one per workplace, gold to coral, the last one mint) | lies along X and spins around it; teal to violet gradient applied as vertex colours in JS |
| GitHub star | `build_ghstar` | five-point gem: rim vertices, raised apex, flat back, brushed gold | upright, spins around Y |
| Knot | `build_knot` | (2,3) torus knot as a curve tube, metallic with thin-film iridescence | tumbles; iridescence set in JS because the glTF exporter only wrote clearcoat |
| Prism | `build_prism` | glass triangular prism, white beam in, five coloured rays out (the five AI designs) | swings back and forth; glass replaced by a transparent physical material for stable rendering in the shared canvas |
| Slicer view | `build_print_layers` | the star cut into 8 horizontal slabs with bmesh bisect and filled caps, pulled apart | rotates while the layers pull apart and stack back together (one node per layer, via `_join`) |
| Printed star | reuses `star.glb` | mint PLA | rotates; layer lines drawn in a shader from object height (exaggerated so they read on screen) |
| Contact (replaced by the bust) | `build_contact` | speech bubble with "..." standing flat on the bed, 60 degree tail (printable without support), hotend with brass nozzle, PEI bed | 3D-printed live: a clipping plane rises as the current layer, the nozzle traces the layer outline (`bubbleSpan`), dots pulse like a typing indicator, then it prints out again |
| AI dancers | `build_claude`, `build_openai`, `build_gemini` | pixel Claude from the site's SVG as blocks; a coin with the OpenAI mark from `openai.jpg` as texture; the Gemini sparkle from its SVG path, extruded with a vertex-colour gradient | one 4 second keyframed clip (`export_animation_mode='SCENE'`) played with an AnimationMixer; also used on the particle front page |

Iterations worth recording:

- **Colour:** emission at high strength turned white under AgX tone mapping, so the helix nodes and the prism rays
  lost their colour. Emission strengths were lowered to 0.5 to 2.2. In the browser the dancers use Neutral tone
  mapping so the brand colours stay true.
- **Contact element:** the first version was a chrome @ glyph. The owner found it looked like the 2000s. Six
  alternatives were proposed (see section 8). The 3D-printed speech bubble was chosen because it ties the contact
  section to the page's own theme.
- **Bubble printability:** the first bubble floated above the bed on its tail, which cannot be printed without
  support. It was redesigned to sit flat on the bed.

### 4.5 Printability check (`check_print`)

The 3D print section quotes real numbers, measured on the merged star scaled to 80 mm across:

| Check | Method | Result |
| --- | --- | --- |
| Closed mesh | count non-manifold edges after the exact boolean union | 0 |
| Size | bounding box scaled to 80 mm | 69.8 x 80 x 6.6 mm |
| Volume | `bmesh.calc_volume` | 4.14 cm³ |
| Overhang | area of faces pointing down more than 45 degrees, above the bed | 0.1 mm² |
| Flat base | area of faces pointing straight down at z = 0 | 920 mm² |

The page states that the slicer and print images are visualisations, not photos.

### 4.6 The marble bust (`trellis_bust.py`, `cutout.py`, `build_bust`)

**Input.** Five photos supplied by the owner plus the portraits already in the repo. Several had sunglasses or a
cap, which hide the eyes and forehead. The 2018 studio portrait (no glasses, even light, 4000 x 6000) was the
best source. It was cropped to head, neck and upper chest (the framing of a bust) and downscaled to 926 x 1024.
The legacy portrait (`designs/legacy/img/Stephan_Thierry.jpg`) was used as a second candidate.

**Background removal.** `cutout.py` runs rembg (u2net) on the CPU and saves an RGBA PNG. TRELLIS skips its own
background removal when the image already has transparency, which matters for memory (below).

**Generation.** `trellis_bust.py gen` loads the TRELLIS image pipeline, encodes the image with DINOv2, samples
the sparse structure (25 steps, cfg 7.5) and the structured latent (25 steps, cfg 3.0), and saves the latent
(`.slat`, feats + coords). `trellis_bust.py dec` loads only the mesh decoder, decodes with FlexiCubes and writes a
PLY. About 7 seconds per sampling stage on the RTX 5080.

**Problems solved on this machine:**

| Problem | Cause | Fix |
| --- | --- | --- |
| Imports fail (kaolin, utils3d, open3d, nvdiffrast) | training and rendering code imported at package level | stub them in the run script; the mesh path never calls them. This also keeps the non-commercial rasterisers (nvdiffrast, the Gaussian rasteriser) out entirely |
| `CUDA error ... flash_fwd_launch_template.h` | xformers picks a Hopper flash-attention kernel that fails on Blackwell | force `MemoryEfficientAttentionCutlassOp` (checked with a block-diagonal mask test first) |
| Access violation / "paging file too small" | Windows has no pagefile, so the commit limit equals RAM, with about 5 GB free | build models directly on the GPU, skip the Gaussian and radiance-field decoders, the owner closed apps (12.6 GB free) |
| rembg "bad allocation" | memory peak with all models loaded | cut out the background beforehand in its own process |
| Decoder out of memory although the GPU reported 7.5 GB free | on Windows (WDDM) GPU allocations also cost host commit | generation and decoding in separate processes |

**Selection.** Nine variants were generated (two photos, several seeds) and rendered from the front and at three
quarters in Workbench with cavity shading on a contact sheet. The variant `studio_bust_s2` was picked for
likeness: goatee, jaw line, expression and collar.

**Finishing in Blender (`build_bust`):**

1. Import PLY, scale to 3.6 units tall, centre, stand on z = 0.
2. Voxel remesh (0.009) to close the mesh, then a light corrective smooth.
3. Hair: the generated strands were flaky, double-sided sheets. Laplacian smoothing did not remove them. They are
   instead pulled with a **Shrinkwrap** modifier, limited to a height-based vertex group, onto a coarse
   (voxel 0.06) and heavily smoothed copy of the head. This turns them into calm, sculpted stone hair. A second
   fine remesh welds the result.
4. Clean-up: drop loose fragments, sand down spikes (difference to a smoothed copy), flatten the crown, and sand
   "needles" (vertices whose faces point in opposite directions).
5. Decimate to about 180,000 faces, smooth shading, marble material (warm white, faint veins, subsurface).
6. Dark stone plinth with a brass plaque reading "STEPHAN THIERRY".

**Output.** `bust.glb` (1.6 MB with meshopt), shown rotating next to the contact heading (first in the hero, moved there on
request so the animated star could return to the hero), and `bust.webp` as fallback. The footer credits
TRELLIS. The photos are not in the repo.

## 5. Formats

| Stage | Format | Notes |
| --- | --- | --- |
| Inputs | SVG polygon coordinates in code, analytic shapes, `openai.jpg`, JPEG/PNG portraits | portraits stay outside the repo |
| TRELLIS intermediates | RGBA PNG (cutout), `.slat` (PyTorch tensors), PLY mesh | in `C:\ai\bust`, outside the repo |
| Fallback renders | WEBP RGBA, written by Blender | 27 to 322 KB each |
| Live models | glTF 2.0 binary (GLB), Y-up, modifiers applied, EXT_meshopt_compression for the element models | the star and the dancers are uncompressed; meshopt roughly halved the helix (985 to 452 KB) and the knot |
| Animation | glTF animation, one sampled clip of 96 frames at 24 fps | dancers |
| Materials | Principled BSDF to glTF PBR + KHR_materials_clearcoat, transmission, emissive_strength | gradients and iridescence that do not export are added in JS |

Model sizes: bust 1.6 MB, helix 452 KB, star 306 KB, knot 241 KB, dancers 168 KB, layers 111 KB,
prism 31 KB, ghstar 9 KB.

## 6. In the browser

- **Hero (`src/main.js`):** its own WebGL renderer for the animated star. Drag rotation with inertia, a slow idle
  spin, a slight lean toward the pointer, and paused when off screen.
- **Everything else (`src/views.js`):** one fixed, full-viewport canvas draws every model into the rectangle of
  its frame with **scissor viewports**, so nine models cost a single WebGL context. Models load when their frame
  is within one screen of the viewport. Each model is centred and fitted to its frame: by bounding sphere, or by
  length for the helix. The `<img>` with the Cycles render stays in the layout and is hidden only when the live
  model is ready.
- **Fallbacks:** without WebGL the Cycles renders remain. With `prefers-reduced-motion` rotation stops and the
  dancers hold a still pose.
- **One bug worth remembering:** the class `.live` collided with an existing CSS rule (the pulsing dot, `width: 7px`)
  and collapsed every frame. It was renamed to `.is-live`.

## 7. Validation

- **Visual review of every Blender step:** low-sample preview renders combined into contact sheets with Pillow,
  inspected before each final render. This caught the misplaced rings, the washed-out emission, the floating
  bubble, the flaky hair and the remaining spikes.
- **Geometry checks:** the non-manifold and printability numbers (section 4.5), loose-part and needle counts on the
  bust, node and rung counts checked against the captions (22 rungs, 10 nodes).
- **Browser checks:** headless Chrome via puppeteer-core at 1440 x 900, 1000 x 900 and 390 x 844. The checks covered
  screenshots of every section and frame, `scrollWidth` equal to the viewport (no sideways scrolling), every model
  marked live, and no 4xx responses or page errors.
- **Live checks after every deploy:** HTTP status of the page and the models, and the same browser check against
  https://protek.dk.
- **License checks before installing anything:** code and weights of every model were read first (section 8).

## 8. Alternatives considered, and why this path

| Decision | Alternatives | Chosen | Why |
| --- | --- | --- | --- |
| How visuals reach the page | only prerendered images; everything real-time | prerendered fallbacks plus live GLBs | Cycles quality and fast loading where WebGL is missing, real interaction where it is not. The owner later asked for every element to rotate live |
| Source of geometry | hand modelling in the Blender UI; imported stock assets | code in `scene.py` run through MCP | reproducible, reviewable in git, and itself the subject of the page |
| One canvas or many | one WebGL context per element (about ten) | one shared canvas with scissor viewports | browsers limit contexts; one context is lighter and avoids lost-context errors |
| Star in real time | separate shard meshes | boolean-merged single mesh, flat facets | overlapping coplanar faces z-fight; the merge is also the printable solid |
| Contact element | chrome @ (rejected as dated); filament spool writing; slicer toolpath view; paper plane folding; default cube modelled into a bubble; soft-body bubble; Claude typing | 3D-printed speech bubble | strongest link to the page's 3D print theme, light to render (one clipping plane) |
| Printed layer lines | real stair-stepped geometry (many slabs) | shader stripes from object height | same look at a fraction of the geometry |
| Bust: method | cloud services (Meshy, Tripo) where the owner uploads the photo; a stylised bust sculpted from face landmarks in Blender | local image-to-3D model | best likeness, and the photos never leave the machine |
| Bust: model | **Hunyuan3D-2** (first recommendation); Stable Fast 3D; TripoSR | **TRELLIS** | Hunyuan3D's license explicitly does not apply in the EU, UK and South Korea and forbids using its output there, so it was removed before any download. TRELLIS is MIT (code and weights) with the best quality of the open options. Stable Fast 3D (Stability Community License) was the fallback; TripoSR (MIT) gives softer faces |
| Bust: TRELLIS dependencies | install nvdiffrast, the Gaussian rasteriser, kaolin | stub them, mesh path only | they are only needed for rendering and texture baking, and some are non-commercial licenses |
| Bust: memory | ask for a pagefile (system change, restart) | lean loading, separate processes, apps closed for the run | no system change needed |
| Bust: hair | keep the generated strands; Laplacian smoothing | shrinkwrap onto a smoothed volume | smoothing does not remove thin double-sided sheets; stone busts have sculpted hair anyway |
| Bust placement | hero viewport (tried first); front page portrait | contact section | the owner wanted the animated star back in the hero; next to "Kontakt" the bust works as a personal sign-off. It replaced the 3D-printed speech bubble |
| Where the design lives | `/blender` | `/designs/blender/` like the other designs | the owner's call once it joined the showcase |

## 9. Reproducing

In Blender 5.2 with the MCP add-on (or the Python console):

```python
exec(open(r'<repo>/designs/blender/blender/scene.py', encoding='utf-8').read())
build_all()              # every element except the bust, in its own collection
render_all(256)          # public/renders/*.webp
export_star_glb()        # merged star + rings
export_element_glbs()    # helix, ghstar, knot, prism, layers (meshopt)
export_dancers_glb()     # also copied to site/public/models for the front page
check_print(80)          # the numbers in the 3D print section
```

The bust (TRELLIS checked out at `C:\ai\trellis`, its own Python 3.12 venv):

```
python designs/blender/blender/cutout.py photo.jpg photo.png
python designs/blender/blender/trellis_bust.py gen photo.png outdir 1,2,3,4,5
python designs/blender/blender/trellis_bust.py dec outdir/photo_s2.slat bust.ply
```

Then in Blender: `build_bust(r'path\to\bust.ply')`, `export_bust_glb()`, `render_one('bust', 256)`.
Finally `powershell -NoProfile -File build.ps1` / `deploy.ps1` from the repo root.

## 10. Known limitations

- The bust is a reconstruction from a single photo. It is recognisable from the front and at three quarters, but
  the back of the head is the model's guess, and the face is softer than in reality.
- The live models are redrawn from their frames' positions every frame. Some browsers may show a slight lag when
  scrolling fast.
- Not tested on a real phone with touch, or in Safari.
- TRELLIS and its environment (several GB) live outside the repo on the build machine. They are only needed to make
  new bust variants.
