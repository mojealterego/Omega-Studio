from pathlib import Path
root=Path(__file__).resolve().parents[1]/'android/app/src/main/assets'
p=root/'index.html'
s=p.read_text(encoding='utf-8')
s=s.replace('<button class="active" data-tab="editor">','<button data-tab="builder"><span>◫</span>AppBuilder</button><button class="active" data-tab="editor">',1)
s=s.replace('<section class="panel active" id="editor">', '''<section class="panel" id="builder">
  <div class="builder-hero">
    <div class="builder-orbit">Ω</div>
    <div class="builder-intro"><p class="eyebrow">OMEGA / SOVEREIGN APP FACTORY</p><h1>AppBuilder <em>Studio</em></h1>
    <p>Twórz aplikacje webowe i natywne Android bez kodowania. Edytuj strukturę, projektuj widoki, sprawdzaj podgląd i eksportuj pełne źródła.</p>
    <div class="builder-badges"><span>NO-CODE</span><span>CODE EXPORT</span><span>WEB + NATIVE ANDROID</span><span>100% LOCAL</span></div></div>
  </div>
  <div class="builder-metrics"><div><small>ŚRODOWISKA</small><b>02</b><span>Web / Android</span></div><div><small>GENEROWANY KOD</small><b>HTML + Java</b><span>Bez zależności runtime</span></div><div><small>MODEL DANYCH</small><b>JSON v1</b><span>Deterministyczny eksport</span></div></div>
  <div class="builder-actions"><button class="gold" id="builderExport">↓ Eksportuj projekt ZIP</button><button id="builderSave">Zapisz projekt</button><button id="builderLoad">Importuj JSON</button><input id="builderImport" type="file" accept="application/json,.json" hidden><button id="builderReset">Nowy projekt</button></div>
  <div class="builder-layout">
    <div class="builder-side">
      <div class="builder-card"><div class="builder-cardhead"><b>01 / Projekt</b><span>USTAWIENIA</span></div>
        <label>Nazwa aplikacji<input id="builderName" maxlength="80" autocomplete="off"></label>
        <label>Identyfikator<input id="builderSlug" maxlength="48" autocomplete="off"></label>
        <label>Pakiet Android<input id="builderPackage" maxlength="128" autocomplete="off"></label>
        <label>Platforma<select id="builderPlatform"><option value="both">Web + Android</option><option value="web">Aplikacja webowa</option><option value="android">Natywna aplikacja Android</option></select></label>
        <label>Motyw<select id="builderTheme"><option value="obsidian-gold">Obsidian &amp; 24K Gold</option><option value="graphite-silver">Graphite &amp; Platinum</option><option value="midnight-blue">Midnight &amp; Sapphire</option></select></label>
      </div>
      <div class="builder-card"><div class="builder-cardhead"><b>02 / Strony</b><button id="builderAddPage">+ Strona</button></div>
        <div id="builderPages" class="builder-pages"></div>
        <label>Tytuł strony<input id="builderPageTitle" maxlength="80"></label>
        <button id="builderRemovePage" class="builder-danger">Usuń stronę</button>
      </div>
    </div>
    <div class="builder-center"><div class="builder-card"><div class="builder-cardhead"><b>03 / Komponenty</b><span>PRZECIĄGNIJ LOGIKĘ</span></div>
      <div class="builder-palette" id="builderPalette"><button data-type="heading">+ Nagłówek</button><button data-type="paragraph">+ Tekst</button><button data-type="card">+ Karta</button><button data-type="button">+ Przycisk</button><button data-type="input">+ Pole</button><button data-type="divider">+ Linia</button></div>
      <div id="builderComponents" class="builder-components"></div>
      <p class="builder-hint">Wybierz element, aby edytować jego właściwości. Zmiany od razu pojawią się w podglądzie.</p>
    </div></div>
    <div class="builder-previewcol"><div class="builder-card"><div class="builder-cardhead"><b>04 / Live Preview</b><span>ODIZOLOWANY</span></div>
      <div class="builder-device"><div class="builder-device-top"><i></i><span>OMEGA APP</span><i></i></div><iframe id="builderPreview" sandbox="" title="Podgląd tworzonej aplikacji"></iframe><div class="builder-device-bottom"><span>◯</span></div></div>
      <div class="builder-previewnote">Podgląd jest odizolowany. Eksport Android generuje rzeczywiste natywne widżety.</div>
    </div></div>
  </div>
  <div class="builder-status" id="builderStatus" role="status">Gotowe do projektowania.</div>
</section>
<section class="panel active" id="editor">''',1)
s=s.replace('<script src="app.js"></script></body></html>','<script src="app.js"></script><script src="builder.js"></script><script src="builder-ui.js"></script></body></html>')
p.write_text(s,encoding='utf-8')
