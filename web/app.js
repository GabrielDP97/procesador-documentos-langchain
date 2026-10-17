const $ = (id) => document.getElementById(id);
let files = [];
let report = null;
let busy = false;
const MAX_SIZE = 1024 * 1024;

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
    const size = element('small', '', file.size < 1024 ? `${file.size} B` : `${Math.ceil(file.size / 1024)} KiB`);
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
    if (file.size > MAX_SIZE) { errors.push(`${file.name}: supera 1 MiB.`); continue; }
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

function fileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name: file.name, content: reader.result.split(',')[1]});
    reader.onerror = () => reject(new Error(`No se pudo leer ${file.name}. Vuelve a seleccionarlo.`));
    reader.readAsDataURL(file);
  });
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
  document.body.classList.add('busy');
  $('results').parentElement.setAttribute('aria-busy', 'true');
  ['example', 'simulate', 'file-input', 'export'].forEach(id => $(id).disabled = true);
  renderFiles();
  $('process').textContent = 'Procesando…';
  message('Leyendo y procesando los documentos en local…');
  try {
    const uploads = await Promise.all(files.map(fileBase64));
    const response = await fetch('/api/process', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({files: uploads, simulate_transient: $('simulate').checked})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'No se pudo procesar el lote.');
    report = value;
    renderReport(value);
    message(value.summary.errors ? 'Lote terminado. Revisa los archivos con error.' : 'Listo. Ya puedes revisar y exportar los resultados.');
  } catch (error) {
    message(error instanceof TypeError ? 'No se pudo conectar. Comprueba que la aplicación sigue abierta en la terminal.' : error.message, true);
  } finally {
    busy = false;
    document.body.classList.remove('busy');
    $('results').parentElement.setAttribute('aria-busy', 'false');
    ['example', 'simulate', 'file-input'].forEach(id => $(id).disabled = false);
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
