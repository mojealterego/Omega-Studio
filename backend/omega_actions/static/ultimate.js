'use strict';
(() => {
  const token = document.querySelector('meta[name="omega-token"]')?.content || '';
  const $ = (id) => document.getElementById(id);
  const set = (id, value) => { const node = $(id); if (node) node.textContent = String(value); };
  const request = async (path, options = {}) => {
    const response = await fetch(path, { ...options, headers: { 'X-OMEGA-Token': token, ...(options.headers || {}) } });
    if (!response.ok) { let detail = response.statusText; try { detail = (await response.json()).detail || detail; } catch (_) {} throw new Error(`${response.status}: ${detail}`); }
    return response;
  };
  const json = async (path, data) => (await request(path, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })).json();
  const download = (blob, filename) => { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000); };
  let generatedHTML = '';
  const showResults = (items) => {
    const root = $('repoResults'); root.replaceChildren();
    for (const item of items) {
      const card = document.createElement('article'); card.className = 'repo-card';
      const title = document.createElement('strong'); title.textContent = item.full_name;
      const meta = document.createElement('small'); meta.textContent = `${item.language || '—'} · ${item.license || 'NOASSERTION'}`;
      const desc = document.createElement('p'); desc.textContent = item.description || 'Bez opisu';
      card.append(title, meta, desc); root.append(card);
    }
    if (!items.length) root.textContent = 'Brak wyników w lokalnym indeksie.';
  };
  const search = async () => { const q = encodeURIComponent($('repoQuery').value); const data = await json(`/api/ultimate/search?q=${q}&limit=50`); set('repoCount', data.total); showResults(data.items); };
  $('crawlButton').addEventListener('click', async () => {
    $('crawlButton').disabled = true; set('crawlStatus', 'Indeksowanie organizacji GitHub…');
    try { const org = encodeURIComponent($('orgName').value.trim()); const pages = Number($('pageCount').value); const data = await json(`/api/ultimate/repositories?organization=${org}&pages=${pages}`); set('crawlStatus', `Zapisano ${data.indexed} rekordów. Łącznie w indeksie: ${data.total}.`); await search(); }
    catch (error) { set('crawlStatus', `Błąd: ${error.message}`); }
    finally { $('crawlButton').disabled = false; }
  });
  $('searchButton').addEventListener('click', () => search().catch(error => set('crawlStatus',error.message)));
  const loadUpstreams = async () => {
    try {
      const data = await json('/api/ultimate/upstreams');
      const list = $('upstreamSelect'), cards = $('upstreamCards');
      list.replaceChildren(); cards.replaceChildren();
      for (const item of data.sources) {
        const option = document.createElement('option'); option.value = item.name;
        option.textContent = `${item.name} · ${item.license}`; list.append(option);
        const card = document.createElement('article'); card.className = 'repo-card';
        const title = document.createElement('strong'); title.textContent = item.name;
        const details = document.createElement('small'); details.textContent = `${item.role} · ${item.license} · ${item.commit.slice(0,12)}`;
        const url = document.createElement('p'); url.textContent = item.repository;
        card.append(title, details, url); cards.append(card);
      }
      set('upstreamStatus', `Katalog: ${data.sources.length} oficjalnych projektów, rewizje SHA przypięte. Źródła nie zostały pobrane.`);
    } catch (error) { set('upstreamStatus', `Błąd katalogu: ${error.message}`); }
  };
  $('upstreamFetch').addEventListener('click', async () => {
    if (!$('upstreamConsent').checked) {
      set('upstreamStatus', 'Zaznacz świadomą zgodę na pobranie i warunki licencji.');
      return;
    }
    const name = $('upstreamSelect').value;
    if (!name) { set('upstreamStatus', 'Wybierz projekt upstream.'); return; }
    $('upstreamFetch').disabled = true;
    set('upstreamStatus', `Pobieranie źródeł ${name}…`);
    try {
      const data = await json('/api/ultimate/upstreams/sync', {name, confirm_network:true});
      set('upstreamStatus', `Pobrano źródła ${data.name} (${data.commit.slice(0,12)}). Bez uruchamiania kodu upstream.`);
    } catch (error) { set('upstreamStatus', `Błąd pobierania: ${error.message}`); }
    finally { $('upstreamFetch').disabled = false; }
  });
  loadUpstreams();
  $('generateButton').addEventListener('click', async () => {
    try { const data = await json('/api/ultimate/nocode', { description: $('appDescription').value }); generatedHTML = data.html; $('nocodePreview').srcdoc = generatedHTML; $('exportButton').disabled = false; set('nocodeStatus', 'Szablon HTML wygenerowany lokalnie. Podgląd izolowany.'); }
    catch (error) { set('nocodeStatus', `Błąd: ${error.message}`); }
  });
  $('exportButton').addEventListener('click', () => { if (generatedHTML) download(new Blob([generatedHTML], {type:'text/html;charset=utf-8'}), 'omega-app.html'); });
  $('analyzeButton').addEventListener('click', async () => {
    $('analyzeButton').disabled = true;
    set('swarmResult','Uruchamianie analizatorów...');
    try { const result = await json('/api/ultimate/analyze', {source:$('swarmSource').value,mode:$('swarmMode').value});
      set('swarmResult',JSON.stringify(result,null,2)); }
    catch (error) { set('swarmResult',`Błąd: ${error.message}`); }
    finally { $('analyzeButton').disabled = false; }
  });
  $('assetButton').addEventListener('click', async () => {
    $('assetButton').disabled = true;
    try { const kind = $('assetKind').value; const response = await request('/api/ultimate/assets', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,text:$('assetText').value})}); const extension = kind === 'gltf' ? 'gltf' : kind; download(await response.blob(),`omega-asset.${extension}`); set('assetStatus',`Wygenerowano asset ${kind.toUpperCase()}.`); }
    catch (error) { set('assetStatus',`Błąd: ${error.message}`); }
    finally { $('assetButton').disabled = false; }
  });
  $('simulateButton').addEventListener('click', async () => {
    $('simulateButton').disabled = true; set('simulationResult','Uruchamianie deterministycznej symulacji…');
    try { const seed = Number($('seed').value); const jobs = Number($('jobs').value); const result = await json(`/api/ultimate/simulate?seed=${seed}&jobs=${jobs}`, {}); set('simulationResult',JSON.stringify({status:result.status,seed:result.seed,jobs:result.jobs,invariants:result.invariants,external_twin:result.external_twin.invariants},null,2)); }
    catch (error) { set('simulationResult',`Błąd: ${error.message}`); }
    finally { $('simulateButton').disabled = false; }
  });
  Promise.all([json('/api/ultimate/status'), json('/api/ultimate/search?q=&limit=1')]).then(([status, search]) => {
    set('systemState', 'LOCAL READY'); set('serverHealth','AKTYWNY'); set('repoCount',search.total);
  }).catch(() => {set('systemState','BACKEND OFFLINE');set('serverHealth','BRAK POŁĄCZENIA');});
})();
