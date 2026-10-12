// Pruebas de enlaces y renderizado con DOM mínimo, sin dependencias ni servidor.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; this.classList = {toggle() {}, add() {}}; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener() {}
  set innerHTML(_) { throw new Error('No se permite innerHTML'); }
}
const elements = new Map();
const context = vm.createContext({URL, Date, console,
  document: {createElement: tag => new Element(tag), getElementById: id => {
    if (!elements.has(id)) elements.set(id, new Element('div'));
    return elements.get(id);
  }},
  fetch: async () => ({ok: true, json: async () => ({})})
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../dashboard/app.js'), 'utf8'), context);
for (const value of ['javascript:alert(1)', 'data:text/html,attack', '//evil.test', 'https://user:pass@example.org', '/relative']) {
  assert.equal(context.safeURL(value), null);
}
assert.equal(context.safeURL('https://example.org/path'), 'https://example.org/path');
for (const value of ['entrada/documentos/../secret', 'entrada/documentos/%2e%2e/secret', 'entrada/documentos/a\\secret', '/entrada/documentos/a.pdf', 'entrada/documentos/a.pdf?x', 'entrada/documentos//a']) {
  assert.equal(context.safePath(value), null);
}
assert.equal(context.safePath('entrada/documentos/informe anual.pdf'), '../entrada/documentos/informe%20anual.pdf');
const hostile = '<img src=x onerror=alert(1)>';
context.records('newsList', [{titulo: hostile, contenido_leido: 'leido', extracto_factual: hostile, url: 'javascript:alert(1)'}]);
assert.equal(elements.get('newsList').children[0].children[0].textContent, hostile);
assert.equal(elements.get('newsList').children[0].children.some(c => c.tag === 'img'), false);
vm.runInContext(`data = {radar: [], biblioteca: [], candidatos: {noticias: [{id: 'seleccionado', seleccionado: true}, {id: 'pendiente', seleccionado: false}]}}; render();`, context);
assert.equal(elements.get('candidateList').children.length, 1);
assert.equal(elements.get('candidateList').children[0].children[0].textContent, 'pendiente');
console.log('Dashboard: enlaces seguros, texto hostil y candidatos pendientes verificados');
