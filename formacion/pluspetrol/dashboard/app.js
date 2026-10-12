'use strict';
const $ = id => document.getElementById(id);
const EMPTY = {perfil: {}, radar: [], biblioteca: [], referencias_pendientes: [], candidatos: {}, actividad: [], advertencias: []};
let data = EMPTY;
let query = '';
let relevance = 'all';
function node(tag, text, cls) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (cls) element.className = cls;
  return element;
}
function safeURL(value) {
  if (typeof value !== 'string' || !/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
function safePath(value) {
  if (typeof value !== 'string' || !value.startsWith('entrada/documentos/') || /[\\%?#\u0000-\u001f]/.test(value)) return null;
  const parts = value.split('/');
  if (parts.some(p => !p || p === '.' || p === '..')) return null;
  return '../' + parts.map(encodeURIComponent).join('/');
}
function link(parent, title, url) {
  if (!url) return;
  const a = node('a', title, 'tag');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  parent.append(a);
}
const list = value => Array.isArray(value) ? value.filter(v => v && typeof v === 'object') : [];
const visible = r => JSON.stringify(r).toLowerCase().includes(query.toLowerCase()) && (relevance === 'all' || (r.relevancia || 'sin_clasificar') === relevance);
function records(id, items, candidate = false) {
  const container = $(id);
  container.replaceChildren();
  if (!items.length) { container.append(node('p', 'Sin registros', 'empty')); return; }
  for (const r of items) {
    const article = node('article', null, 'list-item');
    article.append(node('h3', r.titulo || r.id || 'Sin título', 'item-title'));
    if (candidate) article.append(node('p', r.seleccionado ? 'Seleccionado · pendiente de incorporación o incorporado' : 'Pendiente de selección humana', 'tag amber'));
    const read = r.contenido_leido;
    article.append(node('p', read === 'inaccesible' ? 'Referencia sin contenido leído' : r.extracto_factual || r.resumen || 'Sin resumen disponible', 'item-summary'));
    const details = [
      ['ID', r.id], ['Fuente / institución', r.fuente || r.institucion],
      ['Publicación', r.fecha_publicacion], ['Actualización', r.fecha_actualizacion],
      ['Fecha del documento', r.fecha_documento], ['Consulta', r.fecha_consulta],
      ['Relevancia', r.motivo_relevancia], ['Lectura', read], ['Acceso', r.estado_acceso],
      ['Procedencia / búsqueda', r.busqueda_id], ['Noticia de origen', r.noticia_origen_id],
      ['Documentos relacionados', Array.isArray(r.documentos_relacionados) ? r.documentos_relacionados.join(', ') : null],
      ['URL original', r.url], ['Ruta local', r.ruta_local]
    ];
    for (const [label, value] of details) if (value) article.append(node('p', label + ': ' + String(value), 'item-summary'));
    const meta = node('div', null, 'item-meta');
    link(meta, 'Abrir fuente original', safeURL(r.url));
    link(meta, 'Abrir documento local', safePath(r.ruta_local));
    article.append(meta);
    for (const warning of Array.isArray(r.advertencias) ? r.advertencias : []) article.append(node('p', warning, 'item-summary'));
    container.append(article);
  }
}
function render() {
  const news = list(data.radar), docs = list(data.biblioteca), refs = list(data.referencias_pendientes), activity = list(data.actividad);
  records('newsList', news.filter(visible)); records('documentList', docs.filter(visible));
  records('referenceList', refs.filter(visible));
  records('candidateList', [...list(data.candidatos?.noticias), ...list(data.candidatos?.documentos_detectados)].filter(r => !r.seleccionado).filter(visible), true);
  $('newsCount').textContent = news.length; $('documentCount').textContent = docs.length;
  $('runCount').textContent = activity.length;
  const warnings = Array.isArray(data.advertencias) ? data.advertencias : [];
  $('warningCount').textContent = warnings.length + refs.length;
  $('newsPanelCount').textContent = news.filter(visible).length;
  $('documentPanelCount').textContent = docs.filter(visible).length;
  $('activityPanelCount').textContent = activity.length;
  $('profileName').textContent = data.perfil?.nombre || 'Perfil sin configurar';
  $('profileRole').textContent = [data.perfil?.cargo, data.perfil?.organizacion].filter(Boolean).join(' · ') || 'Completa config/perfil.json';
  $('lastUpdate').textContent = data.ultima_ejecucion ? 'Última ejecución: ' + data.ultima_ejecucion.id + ' · ' + data.ultima_ejecucion.fecha + ' · ' + data.ultima_ejecucion.modo_ejecucion : 'Sin ejecuciones registradas';
  $('researchPeriod').textContent = data.periodo_investigado ? 'Periodo investigado: ' + (data.periodo_investigado.desde || 'sin fecha') + ' → ' + (data.periodo_investigado.hasta || 'sin fecha') : 'Periodo sin definir';
  $('dataBanner').textContent = warnings.join(' · ');
  $('dataBanner').classList.toggle('visible', warnings.length > 0);
  $('activityList').replaceChildren();
  for (const a of activity.slice().reverse()) {
    const item = node('article', null, 'activity');
    item.append(node('p', a.fecha, 'activity-date'), node('p', a.id + ' · ' + a.estado, 'activity-title'), node('p', 'Modo: ' + a.modo_ejecucion + ' · Noticias: ' + a.noticias_procesadas + ' · Documentos: ' + a.documentos_procesados, 'activity-note'));
    $('activityList').append(item);
  }
}
async function load() {
  $('refreshButton').disabled = true;
  try {
    const response = await fetch('data.json?ts=' + Date.now(), {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const payload = await response.json();
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Contrato inválido');
    data = payload;
    $('connectionStatus').textContent = 'Datos conectados'; render();
  } catch {
    data = EMPTY; render(); $('connectionStatus').textContent = 'Vista de espera';
    $('dataBanner').textContent = 'No se pudo cargar data.json. Inicia el servidor local desde la raíz del sistema.';
    $('dataBanner').classList.add('visible');
  } finally { $('refreshButton').disabled = false; }
}
$('refreshButton').addEventListener('click', load);
$('searchInput').addEventListener('input', e => { query = e.target.value.trim(); render(); });
$('relevanceFilter').addEventListener('change', e => { relevance = e.target.value; render(); });
$('clearButton').addEventListener('click', () => { query = ''; relevance = 'all'; $('searchInput').value = ''; $('relevanceFilter').value = 'all'; render(); });
render(); load();
