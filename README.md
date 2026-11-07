# protek.dk

Stephan Thierrys personlige side. Forsiden er partikeldesignet; de andre designs ligger som en showcase under `/designs/`.

## Struktur

| Mappe | URL | Hvad |
| --- | --- | --- |
| `site/` | `/` | Partikler. Three.js GPGPU, GSAP, Lenis (Vite). Har sektionen *Designs* med showcasen. |
| `designs/legacy/` | `/designs/legacy/` | Startpunktet: det klassiske Bootstrap-site, bygget i hånden på én dag. Statisk. |
| `designs/plakat/` | `/designs/plakat/` | Typografisk plakat på [scroll-craft](https://github.com/nateherkai/scroll-craft) (MIT). Statisk. |
| `designs/bauhaus/` | `/designs/bauhaus/` | Bauhaus-legeplads med Matter.js-fysik (Vite). |
| `designs/tidende/` | `/designs/tidende/` | Protek Tidende, avisforside sat live med Pretext (Vite). |
| `designs/ebru/` | `/designs/ebru/` | Ebru, marmorering på vand: WebGPU/TSL stable fluids (Vite). |
| `react/` | `/react/` | ReactJS-præsentationen fra Ditmer Academy 2016. Deployes ikke herfra. |

De fem AI-designs er lavet med AI på 2 timer til sammen; legacy-sitet tog en hel dag i hånden.

## Byg og publicer

```powershell
powershell -NoProfile -File build.ps1    # samler hele sitet i .\dist
powershell -NoProfile -File deploy.ps1   # bygger og publicerer (maal i deploy.config.psd1)
```

Deploy-målet ligger i `deploy.config.psd1`, som ikke er i git. Kopier `deploy.config.example.psd1` til `deploy.config.psd1` og ret `Destination` (webmappen på serveren) og `PublicUrl`.

Alle Vite-projekter bruger `base: './'`, så de virker i enhver undermappe. Lokal udvikling: `npm run dev` i den enkelte mappe.

De gamle adresser `/newdesign/`, `/newdesign2/`, `/newdesign3/` og `/newdesign4/` omdirigerer til de nye.

Skærmbillederne i showcasen ligger i `site/public/img/designs/` (1440×900, webp).
