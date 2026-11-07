# protek.dk

Stephan Thierry's personal site. The front page is the particle design; the other designs live in a showcase under `/designs/`. All text on the site is Danish; code, comments and docs are English.

## Structure

| Folder | URL | What |
| --- | --- | --- |
| `site/` | `/` | Particles. Three.js GPGPU, GSAP, Lenis (Vite). Contains the *Designs* section with the showcase. |
| `designs/legacy/` | `/designs/legacy/` | The starting point: the classic Bootstrap site, built by hand in one day. Static. |
| `designs/plakat/` | `/designs/plakat/` | Typographic poster built on [scroll-craft](https://github.com/nateherkai/scroll-craft) (MIT). Static. |
| `designs/bauhaus/` | `/designs/bauhaus/` | Bauhaus playground with Matter.js physics (Vite). |
| `designs/tidende/` | `/designs/tidende/` | Protek Tidende, a newspaper front page typeset live with Pretext (Vite). |
| `designs/ebru/` | `/designs/ebru/` | Ebru, marbling on water: WebGPU/TSL stable fluids (Vite). |
| `designs/blender/` | `/blender/` | Every 3D element modelled and rendered in Blender by Claude Code via the Blender MCP server; live star as GLB in Three.js (Vite). Includes a section on the 3D-print workflow. Not in the showcase yet. `blender/scene.py` rebuilds the scene and renders: run it in Blender via MCP (`build_all(); render_all(); export_star_glb(); check_print()`). |
| `react/` | `/react/` | The ReactJS presentation from Ditmer Academy 2016. Not deployed from here. |

The five AI designs were made with AI in 2 hours combined; the legacy site took a full day by hand.

## Build and deploy

```powershell
powershell -NoProfile -File build.ps1    # assembles the whole site in .\dist
powershell -NoProfile -File deploy.ps1   # builds and publishes (target in deploy.config.psd1)
```

The deploy target lives in `deploy.config.psd1`, which is not in git. Copy `deploy.config.example.psd1` to `deploy.config.psd1` and set `Destination` (the web folder on the server) and `PublicUrl`.

All Vite projects use `base: './'`, so they work in any subfolder. Local development: `npm run dev` in the individual folder.

The showcase screenshots live in `site/public/img/designs/` (1440×900, webp).
