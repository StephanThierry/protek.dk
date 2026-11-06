# protek.dk

Stephan Thierrys personlige side. Statisk HTML, ingen build-step.

## Nyt design (feature/newdesign)

Siden er bygget om efter [scroll-craft](https://github.com/nateherkai/scroll-craft) (MIT):

- `css/scrollcraft.css` og `js/scrollcraft.js` er motoren, uændret fra scroll-craft. Rediger dem ikke.
- `css/protek.css` er sidens egne farver, typografi og layout.
- `index.html` er semantisk HTML, drevet af `data-sc-*` attributter.

Grammatik: typographic poster. Signaturen er CV-sporet, hvor årstallet i hjørnet følger det kort, der står midt i sporet.

Lokalt: server mappen med en vilkårlig statisk server og åbn `/`.

Det gamle Bootstrap-tema ligger stadig i `css/agency.css` m.fl. og bruges ikke af `index.html`. `react/` er den selvstændige ReactJS-præsentation.
