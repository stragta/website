"""Pruebas aisladas stdlib; datos sintéticos solo en directorios temporales."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from sistema_agentico.project import Project
from sistema_agentico.engine import (build_plan, approve, candidates, consolidate,
                                    validate_project, write, read, fingerprint, merge, stable_id)

SOURCE = Path(__file__).resolve().parents[1]

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'system'
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.p = Project(self.root)
        self.c = build_plan(self.p)
        self.c['plan']['consultas'] = [dict(id='q1', texto='Consulta técnica sintética')]
        write(self.p, 'estado/candidatos_investigacion.json', self.c)
        approve(self.p, 'operador de prueba técnica: apruebo plan')
        self.c = candidates(self.p)

    def record(self, kind='news', ident=None):
        r = dict(id=ident or ('n1' if kind == 'news' else 'd1'), seleccionado=False,
                 titulo='Dato sintético de prueba', url='https://example.org/' + kind,
                 fecha_publicacion=None, fecha_actualizacion=None, fecha_consulta=None,
                 motivo_relevancia='Prueba', temas=[], advertencias=[], busqueda_id='q1',
                 estado_acceso='abierto', contenido_leido='leido')
        if kind == 'news':
            r.update(fuente='Fuente de prueba', extracto_factual='Contenido de prueba', documentos_relacionados=[])
        else:
            r.update(institucion=None, fecha_documento=None, tipo_documento=None, version=None,
                     noticia_origen_id=None, ruta_local=None, huella=None, resumen='Lectura web de prueba')
        return r

    def save(self):
        write(self.p, 'estado/candidatos_investigacion.json', self.c)

    def output(self, agent, records):
        write(self.p, 'resultados/pendientes/' + agent + '.json',
              dict(agente=agent, ejecucion_id=self.c['plan']['id'], estado='completado', registros=records, advertencias=[]))

    def test_approval_is_required(self):
        n = self.record()
        self.c['noticias'] = [n]; self.save()
        self.output('investigador', [n])
        self.assertFalse(validate_project(self.p)['valido'])
        n['seleccionado'] = True; self.save()
        self.assertRaises(ValueError, candidates, self.p)

    def test_selected_unknown_rejected(self):
        self.assertRaises(ValueError, approve, self.p, 'operador de prueba técnica', ['desconocido'])

    def test_zero_results_warns_not_success(self):
        report = validate_project(self.p)
        self.assertTrue(report['valido']); self.assertTrue(report['advertencias'])
        self.assertEqual(consolidate(self.p)['ultima_ejecucion']['estado'], 'parcial')

    def test_download_after_plan_relations_and_idempotence(self):
        n, d = self.record(), self.record('doc')
        n['documentos_relacionados'] = ['d1']; d['noticia_origen_id'] = 'n1'
        self.c['noticias'] = [n]; self.c['documentos_detectados'] = [d]; self.save()
        approve(self.p, 'operador de prueba técnica: selecciono', ['n1', 'd1'])
        path = self.root / 'entrada/documentos/nuevo.txt'
        path.write_text('Contenido descargado después de plan', encoding='utf8')
        d.update(ruta_local='entrada/documentos/nuevo.txt', huella=fingerprint(path), contenido_leido='parcial',
                 estado_acceso='parcial', advertencias=['Solo primera sección leída'])
        self.output('investigador', [n]); self.output('bibliotecario', [d])
        first = consolidate(self.p)
        self.assertEqual(len(first['radar']), 1); self.assertEqual(len(first['biblioteca']), 1)
        self.assertEqual(first['fuentes']['relaciones'][0]['noticia_id'], 'n1')
        self.assertIn('entrada/documentos/nuevo.txt', [x['archivo'] for x in read(self.p, 'estado/estado.json')['inventario']])
        snapshot = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*.json')}
        self.assertEqual(first, consolidate(self.p))
        self.assertEqual(snapshot, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*.json')})

    def test_pending_reference_not_analysed(self):
        d = self.record('doc'); d.update(contenido_leido='inaccesible', estado_acceso='inaccesible', resumen=None, advertencias=['Acceso bloqueado'])
        self.c['documentos_detectados'] = [d]; self.save()
        approve(self.p, 'operador de prueba técnica: selecciono', ['d1'])
        self.output('bibliotecario', [d]); dash = consolidate(self.p)
        self.assertEqual(dash['biblioteca'], []); self.assertEqual(len(dash['referencias_pendientes']), 1)
        self.assertIsNone(dash['referencias_pendientes'][0]['huella'])

    def test_no_fingerprint_without_file(self):
        d = self.record('doc'); d['huella'] = 'a' * 64
        self.c['documentos_detectados'] = [d]; self.save()
        self.assertFalse(validate_project(self.p)['valido'])

    def test_path_traversal_and_symlink_rejected(self):
        d = self.record('doc'); d.update(ruta_local='entrada/documentos/../../config/perfil.json', huella='a'*64)
        self.c['documentos_detectados'] = [d]; self.save()
        self.assertFalse(validate_project(self.p)['valido'])
        outside = Path(self.tmp.name) / 'outside.txt'; outside.write_text('externo')
        link = self.root / 'entrada/documentos/link.txt'; link.symlink_to(outside)
        d.update(ruta_local='entrada/documentos/link.txt', huella=fingerprint(outside)); self.save()
        self.assertFalse(validate_project(self.p)['valido'])

    def test_invalid_types_and_url(self):
        for key, value in [('temas', [1]), ('seleccionado', 'false'), ('fecha_publicacion', 7), ('url', 'javascript:alert(1)'), ('contenido_leido', 'supuesto')]:
            n = self.record(); n[key] = value
            self.c['noticias'] = [n]; self.save()
            self.assertFalse(validate_project(self.p)['valido'], key)

    def test_config_preserved_and_limits_enforced(self):
        cfg = self.p.system(); cfg['propiedad_cliente'] = {'conservar': True}; cfg['radar_noticias']['max_noticias'] = 1
        write(self.p, 'config/sistema.json', cfg)
        n, m = self.record(), self.record(ident='n2'); m['url'] += '/otra'
        self.c['noticias'] = [n, m]; self.save()
        self.assertRaises(ValueError, approve, self.p, 'operador de prueba técnica', ['n1', 'n2'])
        self.assertEqual(self.p.system()['propiedad_cliente'], {'conservar': True})
        for invalid in (0, -1, True, '5'):
            cfg['radar_noticias']['max_noticias'] = invalid; write(self.p, 'config/sistema.json', cfg)
            self.assertFalse(validate_project(self.p)['valido'])

    def test_missing_contract_rejected(self):
        (self.root / 'agentes/investigador.md').unlink()
        self.assertFalse(validate_project(self.p)['valido'])

    def test_document_selection_limit_and_result_count(self):
        cfg = self.p.system(); cfg['biblioteca']['max_documentos_por_ejecucion'] = 1
        write(self.p, 'config/sistema.json', cfg)
        a, b = self.record('doc'), self.record('doc', ident='d2'); b['url'] += '/otra'
        self.c['documentos_detectados'] = [a, b]; self.save()
        self.assertRaises(ValueError, approve, self.p, 'operador de prueba técnica', ['d1', 'd2'])
        approve(self.p, 'operador de prueba técnica', ['d1'])
        self.output('bibliotecario', [a, b])
        report = validate_project(self.p)
        self.assertFalse(report['valido']); self.assertIn('límite', report['errores'][0])

    def test_new_plan_preserves_history_configuration(self):
        cfg = self.p.system(); cfg['propiedad_cliente'] = 'conservar'
        write(self.p, 'config/sistema.json', cfg)
        old = copy.deepcopy(self.c)
        new = build_plan(self.p, new=True)
        self.assertNotEqual(old['plan']['id'], new['plan']['id'])
        self.assertEqual(read(self.p, 'resultados/historial/' + old['plan']['id'] + '-candidatos.json'), old)
        self.assertEqual(self.p.system()['propiedad_cliente'], 'conservar')

    def test_dedup_id_normalized_url_hash(self):
        a = dict(id='a', url='HTTPS://EXAMPLE.ORG/file/?utm_source=test#section', huella=None)
        b = dict(id='b', url='https://example.org/file', huella=None)
        records, aliases, count = merge([], [a, b])
        self.assertEqual(len(records), 1); self.assertEqual(aliases['b'], 'a'); self.assertEqual(count, 1)
        self.assertEqual(stable_id('noticia', a['url']), stable_id('noticia', b['url']))
        a['huella'] = 'x'; b.update(url='https://example.org/other', huella='x')
        self.assertEqual(len(merge([], [a, b])[0]), 1)
        b.update(id='a', huella=None)
        self.assertEqual(len(merge([], [a, b])[0]), 1)

    def test_result_window_and_false_summaries(self):
        n = self.record(); self.c['noticias'] = [n]; self.save()
        approve(self.p, 'operador de prueba técnica', ['n1'])
        n['fecha_publicacion'] = '1900-01-01'; self.output('investigador', [n])
        self.assertFalse(validate_project(self.p)['valido'])
        n.update(fecha_publicacion=None, contenido_leido='inaccesible', advertencias=['Bloqueado'])
        self.output('investigador', [n]); self.assertFalse(validate_project(self.p)['valido'])

if __name__ == '__main__':
    unittest.main()
