"""Empaqueta únicamente una base vacía y comprueba identidad del espejo."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parent

def build(destination):
    def read(name):
        return json.loads((ROOT / name).read_text(encoding='utf8'))
    profile = read('config/perfil.json')
    expected = dict(nombre='', cargo='', organizacion='', campo_interes='', temas_noticias=[],
                    tipos_documentos=[], zona_horaria='America/Guayaquil', idioma='es')
    if profile != expected:
        raise ValueError('El bundle requiere perfil vacío con ocho campos exactos')
    for name in ('radar', 'biblioteca', 'actividad'):
        if read('datos/' + name + '.json') != []:
            raise ValueError('Datos precargados: ' + name)
    if read('datos/fuentes.json') != dict(busquedas=[], registros=[], relaciones=[]):
        raise ValueError('Fuentes precargadas')
    if read('estado/candidatos_investigacion.json') != dict(plan=None, noticias=[], documentos_detectados=[], aprobaciones=[]):
        raise ValueError('Candidatos o aprobaciones precargados')
    state = read('estado/estado.json')
    if state.get('ultima_ejecucion') or state.get('inventario') or state.get('archivos_procesados'):
        raise ValueError('Estado de ejecución precargado')
    for name in ('entrada/noticias', 'entrada/documentos', 'resultados/pendientes', 'resultados/historial'):
        if any(p.is_file() and p.name != '.gitkeep' for p in (ROOT/name).rglob('*')):
            raise ValueError('Entradas o resultados precargados: ' + name)
    if (ROOT/'estado/ejecucion_actual.json').exists():
        raise ValueError('Ejecución antigua presente')
    dash = read('dashboard/data.json')
    for key in ('radar', 'biblioteca', 'actividad', 'advertencias', 'referencias_pendientes'):
        if dash.get(key):
            raise ValueError('Dashboard contiene resultados')
    if dash.get('generado') or dash.get('ultima_ejecucion') or dash.get('perfil') not in ({}, expected):
        raise ValueError('Dashboard contiene ejecución o identidad')
    mirror = ROOT.parents[1] / 'formacion/pluspetrol/dashboard'
    if mirror.exists():
        for file in ('index.html', 'app.js', 'data.json'):
            if (ROOT/'dashboard'/file).read_bytes() != (mirror/file).read_bytes():
                raise ValueError('Espejo divergente: ' + file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as bundle:
        for p in sorted(ROOT.rglob('*')):
            relative = p.relative_to(ROOT)
            if '__pycache__' in relative.parts or p.suffix in ('.pyc', '.zip') or any(part.startswith('.') and part != '.gitkeep' for part in relative.parts):
                continue
            if p.is_symlink():
                raise ValueError('No se permiten symlinks en bundle')
            name = 'sistema_agentico_gerencial/' + relative.as_posix() + ('/' if p.is_dir() else '')
            entry = ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            bundle.writestr(entry, b'' if p.is_dir() else p.read_bytes())
    print(destination)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT.parents[1]/'formacion/pluspetrol/sistema_agentico_gerencial_v0.3_investigacion_limpio.zip')
    build(parser.parse_args().output)
