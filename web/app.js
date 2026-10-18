const $ = (id) => document.getElementById(id);
let files = [];
let report = null;
let busy = false;
const MAX_SIZE = 1024 * 1024;
let cancelled = false;
let currentJob = null;
let currentUpload = null;

function message(text, error = false) {
  $('message').textContent = text;
  $('message').classList.toggle('error', error);
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function renderFiles() {
  $('file-list').replaceChildren();
  files.forEach((file, index) => {
    const li = element('li');
    const name = element('span', 'file-name', file.name);
    name.title = file.name;
    const size = element('small', '', file.size < 1024 ? `${file.size} B` : `${(file.size / 1024 / 1024).toFixed(1)} MiB`);
    const remove = element('button', '', '×');
    remove.setAttribute('aria-label', `Quitar ${file.name}`);
    remove.disabled = busy;
    remove.onclick = () => { files.splice(index, 1); renderFiles(); };
    li.append(name, size, remove);
    $('file-list').append(li);
  });
  $('file-count').textContent = files.length ? `${files.length} ${files.length === 1 ? 'archivo seleccionado' : 'archivos seleccionados'}` : 'Ningún archivo seleccionado';
  $('process').disabled = busy || !files.length;
  $('clear').disabled = busy || !files.length;
}
function addFiles(incoming) {
  if (busy) return;
  const errors = [];
  for (const file of incoming) {
    if (!/\.(txt|md|pdf)$/i.test(file.name)) { errors.push(`${file.name}: solo se admiten TXT, Markdown y PDF.`); continue; }
    if (file.size > MAX_SIZE * (/\.pdf$/i.test(file.name) ? 150 : 1)) { errors.push(`${file.name}: supera el límite (PDF 150 MiB; texto 1 MiB).`); continue; }
    if (files.length >= 10) { errors.push('El lote ya tiene 10 archivos.'); break; }
    files.push(file);
  }
  renderFiles();
  message(errors.join('\n'), !!errors.length);
}
$('file-input').addEventListener('change', (event) => { addFiles(event.target.files); event.target.value = ''; });
$('file-input').addEventListener('focus', () => $('drop-zone').style.outline = '3px solid #789c7e');
$('file-input').addEventListener('blur', () => $('drop-zone').style.outline = '');
['dragenter', 'dragover'].forEach(type => $('drop-zone').addEventListener(type, event => { event.preventDefault(); $('drop-zone').classList.add('dragging'); }));
['dragleave', 'drop'].forEach(type => $('drop-zone').addEventListener(type, event => { event.preventDefault(); $('drop-zone').classList.remove('dragging'); }));
$('drop-zone').addEventListener('drop', event => addFiles(event.dataTransfer.files));
window.addEventListener('dragover', event => event.preventDefault());
window.addEventListener('drop', event => event.preventDefault());
$('clear').onclick = () => { files = []; renderFiles(); message(''); };
$('example').onclick = () => addFiles([new File(['# Un pequeño jardín de ideas\n\nLos documentos guardan ideas. Ordenar las ideas ayuda a convertir los documentos en proyectos.\n\nUn proyecto local permite explorar texto sin enviar documentos a servicios externos.\n'], 'ejemplo.md', {type: 'text/markdown'})]);

function showProgress(text, done, total) {
  $('progress-status').textContent = text;
  $('progress-bar').value = total ? 100 * done / total : 0;
}
function uploadFile(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    currentUpload = xhr;
    xhr.open('POST', '/api/jobs');
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
    xhr.setRequestHeader('X-OCR-Languages', $('languages').value);
    xhr.setRequestHeader('X-Simulate', String($('simulate').checked));
    xhr.upload.onprogress = e => showProgress(`Subiendo ${file.name}…`, e.loaded, e.total);
    xhr.onload = () => {
      currentUpload = null;
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status !== 202) throw new Error(data.error || 'No se pudo subir el archivo.');
        resolve(data.id);
      } catch (error) { reject(error); }
    };
    xhr.onerror = () => reject(new Error('Se ha perdido la conexión con la aplicación local.'));
    xhr.onabort = () => reject(new Error('Subida cancelada.'));
    xhr.send(file);
  });
}
$('cancel').onclick = async () => {
  cancelled = true;
  $('cancel').disabled = true;
  if (currentUpload) currentUpload.abort();
  message('Cancelando… La página de OCR actual puede tardar hasta 20 segundos en terminar.');
  if (currentJob) {
    try { await fetch(`/api/jobs/${currentJob}/cancel`, {method: 'POST'}); }
    catch { message('No se pudo confirmar la cancelación. Comprueba que el servidor sigue abierto.', true); }
  }
};
async function awaitJob(id) {
  while (true) {
    const response = await fetch(`/api/jobs/${id}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || 'No se encuentra el trabajo.');
    if (job.status === 'done' || job.status === 'cancelled') return job.result;
    if (job.languages) $('languages').value = job.languages;
    const p = job.progress;
    showProgress(`${job.name} · ${job.status === 'queued' ? 'En espera' : p.stage} · ${p.done} / ${p.total}`, p.done, p.total);
    await new Promise(resolve => setTimeout(resolve, 750));
  }
}
function renderReport(value) {
  $('empty').hidden = true;
  $('summary').hidden = false;
  $('summary').textContent = `${value.summary.ok} ${value.summary.ok === 1 ? 'completado' : 'completados'} · ${value.summary.errors} con error · ${value.summary.total} en total`;
  $('results').replaceChildren();
  for (const result of value.results) {
    const card = element('article', 'result-card');
    const heading = element('div', 'result-header');
    heading.append(element('h3', '', result.name), element('span', `badge ${result.status === 'ok' ? '' : 'failed'}`, result.status === 'ok' ? 'Completado' : 'No procesado'));
    card.append(heading, element('p', 'attempts', `${result.attempts} ${result.attempts === 1 ? 'intento' : 'intentos'} de procesamiento${result.demo ? ' · Simulación activada' : ''}`));
    if (result.status === 'error') {
      card.append(element('p', 'result-error', result.error));
    } else {
      if (result.source?.format === 'pdf') {
        card.append(element('p', 'preview', `PDF · ${result.source.pages} ${result.source.pages === 1 ? 'página' : 'páginas'} · Análisis del texto extraído`));
        if (result.source.ocr_pages?.length) card.append(element('p', 'preview', `OCR local · ${result.source.ocr_pages.length} ${result.source.ocr_pages.length === 1 ? 'página reconocida' : 'páginas reconocidas'} · ${(result.source.ocr_languages || []).map(code => ({spa: "Español", eng: "Inglés", deu: "Alemán"})[code] || code).join(" + ")}`));
      }
      for (const warning of result.warnings || []) card.append(element('p', 'result-warning', warning));
      const stats = element('div', 'stats');
      for (const [key, label] of [['words', 'Palabras'], ['characters', 'Caracteres'], ['lines', 'Líneas'], ['paragraphs', 'Párrafos']]) {
        const stat = element('div', 'stat');
        stat.append(element('strong', '', result.statistics[key].toLocaleString('es-ES')), element('span', '', label));
        stats.append(stat);
      }
      card.append(stats, element('h4', '', 'Palabras frecuentes'));
      const keywords = element('div', 'keywords');
      for (const item of result.keywords) {
        const tag = element('span', 'keyword', item.word);
        tag.append(element('small', '', `×${item.count}`));
        keywords.append(tag);
      }
      if (!result.keywords.length) keywords.append(element('p', 'preview', 'No hay suficientes palabras relevantes.'));
      card.append(keywords, element('h4', '', 'Vista previa · Primer párrafo'), element('p', 'preview', result.preview));
    }
    $('results').append(card);
  }
  $('export').disabled = false;
}
$('process').onclick = async () => {
  if (busy || !files.length) return;
  busy = true;
  cancelled = false;
  $('job-progress').hidden = false;
  $('cancel').disabled = false;
  document.body.classList.add('busy');
  $('results').parentElement.setAttribute('aria-busy', 'true');
  ['example', 'simulate', 'file-input', 'export', 'languages'].forEach(id => $(id).disabled = true);
  renderFiles();
  $('process').textContent = 'Procesando…';
  message('Leyendo y procesando en local… El OCR de documentos escaneados puede tardar unos minutos.');
  try {
    const results = [];
    for (const file of files) {
      if (cancelled) break;
      currentJob = await uploadFile(file);
      sessionStorage.setItem("documento-job", currentJob);
      if (cancelled) await fetch(`/api/jobs/${currentJob}/cancel`, {method: 'POST'});
      results.push(await awaitJob(currentJob));
      sessionStorage.removeItem("documento-job");
      currentJob = null;
    }
    const value = {version: 1, mode: 'local-deterministic', results,
      summary: {total: results.length, ok: results.filter(r => r.status === 'ok').length,
        errors: results.filter(r => r.status !== 'ok').length}};
    report = value;
    renderReport(value);
    message(cancelled ? 'Lote cancelado. Se conservan los resultados ya completados.' : value.summary.errors ? 'Lote terminado. Revisa los archivos con error.' : 'Listo. Ya puedes revisar y exportar los resultados.');
  } catch (error) {
    message(error instanceof TypeError ? 'No se pudo conectar. Comprueba que la aplicación sigue abierta en la terminal.' : error.message, true);
  } finally {
    busy = false;
    currentJob = null;
    currentUpload = null;
    $('job-progress').hidden = true;
    document.body.classList.remove('busy');
    $('results').parentElement.setAttribute('aria-busy', 'false');
    ['example', 'simulate', 'file-input', 'languages'].forEach(id => $(id).disabled = false);
    $('export').disabled = !report;
    $('process').replaceChildren(document.createTextNode('Procesar documentos '), element('span', '', '→'));
    renderFiles();
  }
};
$('export').onclick = () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json;charset=utf-8'}));
  const link = element('a');
  link.href = url;
  link.download = `documentos-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};


async function recoverJob() {
  const id = sessionStorage.getItem('documento-job');
  if (!id || !/^[a-f0-9]{32}$/.test(id)) return;
  busy = true;
  currentJob = id;
  cancelled = false;
  $('job-progress').hidden = false;
  $('cancel').disabled = false;
  ['example', 'simulate', 'file-input', 'languages'].forEach(key => $(key).disabled = true);
  renderFiles();
  message('Recuperando el progreso del documento…');
  try {
    const result = await awaitJob(id);
    report = {version: 1, mode: 'local-deterministic', results: [result],
      summary: {total: 1, ok: result.status === 'ok' ? 1 : 0, errors: result.status === 'ok' ? 0 : 1}};
    renderReport(report);
    sessionStorage.removeItem('documento-job');
    message(cancelled ? 'Trabajo cancelado.' : result.status === 'ok' ? 'Documento terminado. Ya puedes exportar el resultado.' : 'Documento terminado con error. Revisa el resultado.');
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
    currentJob = null;
    $('job-progress').hidden = true;
    ['example', 'simulate', 'file-input', 'languages'].forEach(key => $(key).disabled = false);
    renderFiles();
  }
}
recoverJob();
