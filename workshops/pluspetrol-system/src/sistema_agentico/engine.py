"""Estado, aprobaciones y archivos locales. Sin integración web ni modelos."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4
from .io import read_json, write_json, utc_now, fingerprint

CANDIDATES = 'estado/candidatos_investigacion.json'
GROUPS = {'investigador': 'noticias', 'bibliotecario': 'documentos_detectados'}
DATASETS = {'investigador': 'radar', 'bibliotecario': 'biblioteca'}
NULLTEXT = (str, type(None))
COMMON = dict(id=str, titulo=str, url=NULLTEXT, fecha_publicacion=NULLTEXT,
              fecha_actualizacion=NULLTEXT, fecha_consulta=NULLTEXT, motivo_relevancia=str,
              temas=list, advertencias=list, busqueda_id=str, estado_acceso=str, contenido_leido=str)
NEWS = dict(fuente=str, extracto_factual=NULLTEXT, documentos_relacionados=list)
DOCS = dict(institucion=NULLTEXT, fecha_documento=NULLTEXT, tipo_documento=NULLTEXT,
            version=NULLTEXT, noticia_origen_id=NULLTEXT, ruta_local=NULLTEXT, huella=NULLTEXT, resumen=NULLTEXT)
PROFILE = dict(nombre=str, cargo=str, organizacion=str, campo_interes=str,
               temas_noticias=list, tipos_documentos=list, zona_horaria=str, idioma=str)

def read(p, name, default=None):
    return read_json(p.root / name, default)

def write(p, name, value):
    write_json(p.root / name, value)

def normalized_url(value):
    if value is None:
        return None
    parts = urlsplit(value)
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('URL debe ser HTTP(S), con host y sin credenciales')
    host = parts.hostname.lower()
    port = parts.port
    if port and (parts.scheme.lower(), port) not in (('http', 80), ('https', 443)):
        host += ':' + str(port)
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid'))
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip('/') or '/', urlencode(query), ''))

def stable_id(kind, url):
    return kind + '-' + hashlib.sha256(normalized_url(url).encode()).hexdigest()[:16]

def local_path(p, value, folder='documentos'):
    if not isinstance(value, str) or '\\' in value or '%' in value:
        raise ValueError('Ruta local inválida')
    parts = value.split('/')
    if parts[:2] != ['entrada', folder] or any(x in ('', '.', '..') for x in parts):
        raise ValueError('Ruta fuera de entrada/' + folder)
    target = (p.root / value).resolve()
    target.relative_to((p.root / 'entrada' / folder).resolve())
    target.relative_to(p.root.resolve())
    if not target.is_file():
        raise ValueError('Archivo local inexistente: ' + value)
    return target

def inventory(p):
    items = []
    for folder in ('noticias', 'documentos'):
        for path in sorted((p.root / 'entrada' / folder).rglob('*')):
            if path.is_file() and not path.name.startswith('.'):
                name = path.relative_to(p.root).as_posix()
                safe = local_path(p, name, folder)
                items.append(dict(archivo=name, huella=fingerprint(safe), tamano_bytes=safe.stat().st_size))
    return items

def fields(value, contract, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' debe ser objeto')
    for key, typ in contract.items():
        if key not in value or not isinstance(value[key], typ):
            raise ValueError(label + ': tipo inválido o falta ' + key)
    for key in ('temas', 'advertencias', 'documentos_relacionados', 'temas_noticias', 'tipos_documentos'):
        if key in value and not all(isinstance(x, str) for x in value[key]):
            raise ValueError(label + ': ' + key + ' debe contener textos')

def check_record(p, r, agent, candidate=False):
    fields(r, {**COMMON, **(NEWS if agent == 'investigador' else DOCS)}, agent)
    if not r['id'] or not r['titulo'] or not r['busqueda_id']:
        raise ValueError('id, título y búsqueda deben ser no vacíos')
    if candidate and type(r.get('seleccionado')) is not bool:
        raise ValueError('seleccionado debe ser bool')
    if r.get('relevancia') is not None and r['relevancia'] not in ('alta', 'media', 'baja'):
        raise ValueError('Relevancia opcional inválida')
    if r['contenido_leido'] not in ('leido', 'parcial', 'inaccesible'):
        raise ValueError('contenido_leido inválido')
    if r['estado_acceso'] not in ('abierto', 'parcial', 'inaccesible', 'pendiente'):
        raise ValueError('estado_acceso inválido')
    normalized_url(r['url'])
    for key in ('fecha_publicacion', 'fecha_actualizacion', 'fecha_consulta', 'fecha_documento'):
        if r.get(key) is not None:
            datetime.fromisoformat(r[key].replace('Z', '+00:00'))
    if r['contenido_leido'] != 'leido' and not r['advertencias']:
        raise ValueError('Lectura parcial/inaccesible requiere advertencias')
    content = r.get('extracto_factual') if agent == 'investigador' else r['resumen']
    if r['contenido_leido'] == 'inaccesible' and content:
        raise ValueError('No se puede resumir contenido inaccesible')
    if agent == 'bibliotecario':
        if r['ruta_local'] is None:
            if r['huella'] is not None:
                raise ValueError('Sin archivo no puede existir huella local')
            if r['url'] is None:
                raise ValueError('Documento requiere URL o archivo local')
        elif r['huella'] != fingerprint(local_path(p, r['ruta_local'])):
            raise ValueError('Huella incorrecta: ' + r['ruta_local'])
    elif r['url'] is None:
        raise ValueError('Noticia requiere URL')

def candidates(p):
    c = read(p, CANDIDATES)
    fields(c, dict(plan=dict, noticias=list, documentos_detectados=list, aprobaciones=list), 'candidatos')
    plan = c['plan']
    fields(plan, dict(id=str, aprobado=bool, consultas=list, fuentes_prioritarias=list,
                     periodo=dict, modo_ejecucion=str, herramientas=dict), 'plan')
    if not plan['id'] or any(x in plan['id'] for x in '/\\.'):
        raise ValueError('ID de plan inseguro')
    if plan['modo_ejecucion'] not in ('secuencial', 'delegacion_real'):
        raise ValueError('Modo de ejecución inválido')
    fields(plan['periodo'], dict(desde=str, hasta=str), 'periodo')
    start, end = (datetime.fromisoformat(plan['periodo'][k]) for k in ('desde', 'hasta'))
    if start > end:
        raise ValueError('Periodo invertido')
    for key in ('busqueda_web', 'navegacion', 'descarga'):
        if type(plan['herramientas'].get(key)) is not bool:
            raise ValueError('Capacidad debe ser bool: ' + key)
    if not all(isinstance(x, str) for x in plan['fuentes_prioritarias']):
        raise ValueError('Fuentes prioritarias deben ser textos')
    query_ids = set()
    for q in plan['consultas']:
        fields(q, dict(id=str, texto=str), 'consulta')
        if not q['id'] or q['id'] in query_ids or not q['texto']:
            raise ValueError('Consulta vacía o ID duplicado')
        query_ids.add(q['id'])
    ids = set()
    for agent, group in GROUPS.items():
        for r in c[group]:
            check_record(p, r, agent, True)
            if r['id'] in ids or r['busqueda_id'] not in query_ids:
                raise ValueError('ID duplicado o búsqueda inexistente')
            ids.add(r['id'])
    docs = {r['id'] for r in c['documentos_detectados']}
    news = {r['id'] for r in c['noticias']}
    for r in c['noticias']:
        if not set(r['documentos_relacionados']) <= docs:
            raise ValueError('Documento relacionado inexistente')
    for r in c['documentos_detectados']:
        if r['noticia_origen_id'] is not None and r['noticia_origen_id'] not in news:
            raise ValueError('Noticia origen inexistente')
    approved_ids = set()
    plan_evidence = False
    for a in c['aprobaciones']:
        fields(a, dict(tipo=str, ids=list, fecha=str, entrada_usuario=str), 'aprobación')
        if not a['entrada_usuario'].strip() or not all(isinstance(x, str) for x in a['ids']):
            raise ValueError('Aprobación sin entrada explícita')
        datetime.fromisoformat(a['fecha'].replace('Z', '+00:00'))
        if a['tipo'] == 'plan' and a['ids'] == [plan['id']]:
            plan_evidence = True
        elif a['tipo'] == 'seleccion' and set(a['ids']) <= ids:
            approved_ids.update(a['ids'])
        else:
            raise ValueError('Aprobación inválida')
    if plan['aprobado'] != plan_evidence:
        raise ValueError('Aprobación del plan sin evidencia coincidente')
    for group in GROUPS.values():
        for r in c[group]:
            if r['seleccionado'] != (r['id'] in approved_ids):
                raise ValueError('Selección sin aprobación coincidente: ' + r['id'])
    if (ids or approved_ids) and not plan['aprobado']:
        raise ValueError('Investigar requiere plan aprobado')
    limits = {'noticias': p.system()['radar_noticias']['max_noticias'],
              'documentos_detectados': p.system()['biblioteca']['max_documentos_por_ejecucion']}
    for group, limit in limits.items():
        if sum(r['seleccionado'] for r in c[group]) > limit:
            raise ValueError('Selección supera límite configurado: ' + group)
    return c

def build_plan(p, new=False, mode='secuencial'):
    old = read(p, CANDIDATES)
    if old and old.get('plan') and not new:
        return candidates(p)
    if old and old.get('plan'):
        candidates(p)
        write(p, 'resultados/historial/' + old['plan']['id'] + '-candidatos.json', old)
    now = datetime.now(timezone.utc).date()
    settings = p.system()
    defaults = dict(radar_noticias=dict(busqueda_activa=True, ventana_dias=7, max_noticias=5, requiere_aprobacion=True),
                    biblioteca=dict(max_documentos_por_ejecucion=3, descargar_originales=True, conservar_referencias_inaccesibles=True))
    for key, values in defaults.items():
        section = settings.setdefault(key, {})
        for k, v in values.items():
            section.setdefault(k, v)
    write(p, 'config/sistema.json', settings)
    c = dict(plan=dict(id='run-' + uuid4().hex[:12], aprobado=False,
                       periodo=dict(desde=(now - timedelta(days=settings['radar_noticias']['ventana_dias'] - 1)).isoformat(), hasta=now.isoformat()),
                       consultas=[], fuentes_prioritarias=[], modo_ejecucion=mode,
                       herramientas=dict(busqueda_web=False, navegacion=False, descarga=False)),
             noticias=[], documentos_detectados=[], aprobaciones=[])
    write(p, CANDIDATES, c)
    return c

def approve(p, message, ids=None):
    if not message.strip():
        raise ValueError('Registre la entrada explícita del usuario')
    c = candidates(p)
    if ids is None:
        c['plan']['aprobado'] = True
        ids = [c['plan']['id']]
        kind = 'plan'
    else:
        if not c['plan']['aprobado']:
            raise ValueError('Primero apruebe el plan')
        all_records = c['noticias'] + c['documentos_detectados']
        if not set(ids) <= {r['id'] for r in all_records}:
            raise ValueError('ID de candidato desconocido')
        for r in all_records:
            if r['id'] in ids:
                r['seleccionado'] = True
        kind = 'seleccion'
    event = dict(tipo=kind, ids=ids, fecha=utc_now(), entrada_usuario=message)
    if not any(a['tipo'] == kind and a['ids'] == ids and a['entrada_usuario'] == message for a in c['aprobaciones']):
        c['aprobaciones'].append(event)
    if kind == 'seleccion':
        limits = {'noticias': p.system()['radar_noticias']['max_noticias'],
                  'documentos_detectados': p.system()['biblioteca']['max_documentos_por_ejecucion']}
        if any(sum(r['seleccionado'] for r in c[g]) > limit for g, limit in limits.items()):
            raise ValueError('Selección supera límite configurado')
    write(p, CANDIDATES, c)
    return c

def results(p, c):
    output = {}
    for agent, group in GROUPS.items():
        value = read(p, 'resultados/pendientes/' + agent + '.json')
        selected = {r['id']: r for r in c[group] if r['seleccionado']}
        if value is None:
            if selected:
                raise ValueError('Falta resultado de ' + agent)
            continue
        fields(value, dict(agente=str, ejecucion_id=str, estado=str, registros=list, advertencias=list), agent)
        if value['agente'] != agent or value['estado'] not in ('completado', 'parcial', 'bloqueado'):
            raise ValueError('Agente o estado incorrecto')
        if value['ejecucion_id'] != c['plan']['id']:
            raise ValueError('Resultado de otra ejecución')
        if not all(isinstance(x, str) for x in value['advertencias']):
            raise ValueError('Advertencias deben ser textos')
        limit = p.system()['radar_noticias']['max_noticias'] if agent == 'investigador' else p.system()['biblioteca']['max_documentos_por_ejecucion']
        if len(value['registros']) > limit:
            raise ValueError('Resultado supera límite configurado: ' + agent)
        if len({r.get('id') for r in value['registros'] if isinstance(r, dict)}) != len(value['registros']):
            raise ValueError('IDs duplicados o registros inválidos en resultado')
        for r in value['registros']:
            check_record(p, r, agent)
            candidate = selected.get(r['id'])
            if candidate is None or not c['plan']['aprobado']:
                raise ValueError('Resultado no seleccionado: ' + r['id'])
            for key in ('url', 'busqueda_id', 'documentos_relacionados', 'noticia_origen_id'):
                if key in candidate and r[key] != candidate[key]:
                    raise ValueError('Procedencia cambió: ' + key)
            if agent == 'investigador' and r['fecha_publicacion']:
                if not c['plan']['periodo']['desde'] <= r['fecha_publicacion'][:10] <= c['plan']['periodo']['hasta']:
                    raise ValueError('Noticia fuera del periodo aprobado')
            if agent == 'investigador' and r['contenido_leido'] == 'inaccesible':
                raise ValueError('Noticia sin fuente abierta no puede incorporarse')
        output[agent] = value
    return output

def merge(existing, incoming):
    records, aliases, duplicates = [dict(x) for x in existing], {}, 0
    def keys(r):
        return {('id', r['id'])} | ({('url', normalized_url(r['url']))} if r.get('url') else set()) | ({('huella', r['huella'])} if r.get('huella') else set())
    for r in incoming:
        matches = [i for i, old in enumerate(records) if keys(old) & keys(r)]
        if matches:
            i = matches[0]
            aliases[r['id']] = records[i]['id']
            if records[i]['id'] == r['id']:
                records[i] = dict(r)
            else:
                duplicates += 1
        else:
            records.append(dict(r))
            aliases[r['id']] = r['id']
    return records, aliases, duplicates

def validate_project(p):
    errors, warnings = [], []
    try:
        profile = p.profile()
        fields(profile, PROFILE, 'perfil')
        if set(profile) != set(PROFILE):
            raise ValueError('Perfil debe tener exactamente ocho campos')
        system = p.system()
        for section, keys in {'radar_noticias': ['ventana_dias', 'max_noticias'], 'biblioteca': ['max_documentos_por_ejecucion']}.items():
            for key in keys:
                value = system[section][key]
                if type(value) is not int or value <= 0:
                    raise ValueError('Opción debe ser entero positivo: ' + key)
        for section, keys in {'radar_noticias': ['busqueda_activa', 'requiere_aprobacion'], 'biblioteca': ['descargar_originales', 'conservar_referencias_inaccesibles']}.items():
            for key in keys:
                if type(system[section][key]) is not bool:
                    raise ValueError('Opción debe ser bool: ' + key)
        for agent in ('investigador', 'bibliotecario', 'coordinador'):
            contract = system['agentes'][agent]['contrato']
            path = (p.root / contract).resolve()
            path.relative_to(p.root.resolve())
            if not path.is_file():
                raise ValueError('Falta contrato: ' + agent)
        empty = read(p, CANDIDATES)
        if empty == dict(plan=None, noticias=[], documentos_detectados=[], aprobaciones=[]):
            c = empty
            output = {}
            if any((p.root / ('resultados/pendientes/' + a + '.json')).exists() for a in GROUPS):
                raise ValueError('Resultados sin plan aprobado')
        else:
            c = candidates(p)
            output = results(p, c)
        inventory(p)
        if not any(v['registros'] for v in output.values()):
            warnings.append('Cero resultados reales; no acredita investigación exitosa')
        for a, ds in DATASETS.items():
            dataset = read(p, 'datos/' + ds + '.json', [])
            if not isinstance(dataset, list):
                raise ValueError('Dataset debe ser lista: ' + ds)
            for r in dataset:
                check_record(p, r, a)
        for group in GROUPS.values():
            for r in c[group]:
                if not r['seleccionado']:
                    warnings.append('Candidato pendiente: ' + r['id'])
        for agent, group in GROUPS.items():
            returned = {r['id'] for r in output.get(agent, {}).get('registros', [])}
            for r in c[group]:
                if r['seleccionado'] and r['id'] not in returned:
                    warnings.append('Seleccionado sin resultado: ' + r['id'])
        for v in output.values():
            warnings.extend(v['advertencias'])
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        errors.append(str(e))
    return dict(valido=not errors, errores=errors, advertencias=warnings)

def consolidate(p):
    check = validate_project(p)
    if check['errores']:
        raise ValueError('; '.join(check['errores']))
    c = candidates(p)
    if not c['plan']['aprobado']:
        raise ValueError('Consolidación requiere plan aprobado')
    output, inv = results(p, c), inventory(p)
    radar, news_alias, ndup = merge(read(p, 'datos/radar.json', []), output.get('investigador', {}).get('registros', []))
    library, doc_alias, ddup = merge(read(p, 'datos/biblioteca.json', []), output.get('bibliotecario', {}).get('registros', []))
    for r in radar:
        r['documentos_relacionados'] = list(dict.fromkeys(doc_alias.get(i, i) for i in r['documentos_relacionados']))
    for r in library:
        r['noticia_origen_id'] = news_alias.get(r['noticia_origen_id'], r['noticia_origen_id'])
    pending = [r for r in library if r['contenido_leido'] == 'inaccesible' or r['estado_acceso'] == 'pendiente']
    warnings = list(dict.fromkeys(check['advertencias'] + [w for v in output.values() for r in v['registros'] for w in r['advertencias']]))
    sources = read(p, 'datos/fuentes.json', dict(busquedas=[], registros=[], relaciones=[]))
    for query in c['plan']['consultas']:
        q = {**query, 'ejecucion_id': c['plan']['id']}
        if q not in sources['busquedas']:
            sources['busquedas'].append(q)
    for kind, records in (('noticia', radar), ('documento', library)):
        for r in records:
            f = dict(id=r['id'], tipo=kind, url=r['url'], ruta_local=r.get('ruta_local'), fecha_consulta=r['fecha_consulta'], busqueda_id=r['busqueda_id'])
            sources['registros'] = [s for s in sources['registros'] if s['id'] != r['id']] + [f]
    for r in library:
        relation = dict(busqueda_id=r['busqueda_id'], noticia_id=r['noticia_origen_id'], documento_id=r['id'])
        if relation not in sources['relaciones']:
            sources['relaciones'].append(relation)
    for r in radar:
        for doc in r['documentos_relacionados']:
            relation = dict(busqueda_id=r['busqueda_id'], noticia_id=r['id'], documento_id=doc)
            if relation not in sources['relaciones']:
                sources['relaciones'].append(relation)
    signature = hashlib.sha256(json.dumps(dict(c=c, r=output, inventario=inv), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    history = 'resultados/historial/' + c['plan']['id'] + '-' + signature[:16] + '.json'
    if read(p, history) is not None:
        return read(p, 'dashboard/data.json')
    activity = read(p, 'datos/actividad.json', [])
    event = dict(id=c['plan']['id'], fecha=utc_now(), tipo='ejecucion',
                 estado='parcial' if warnings or pending or any(v['estado'] != 'completado' for v in output.values()) else 'completado',
                 modo_ejecucion=c['plan']['modo_ejecucion'], agentes_ejecutados=list(output),
                 noticias_procesadas=len(output.get('investigador', {}).get('registros', [])),
                 documentos_procesados=len(output.get('bibliotecario', {}).get('registros', [])),
                 duplicados_omitidos=ndup + ddup, advertencias=warnings)
    activity = [a for a in activity if a['id'] != event['id']] + [event]
    dashboard = dict(generado=event['fecha'], perfil=p.profile(), periodo_investigado=c['plan']['periodo'],
                     ultima_ejecucion=event, radar=radar, biblioteca=[r for r in library if r not in pending],
                     referencias_pendientes=pending, candidatos={g: c[g] for g in GROUPS.values()},
                     fuentes=sources, actividad=activity, advertencias=warnings,
                     resumen=dict(noticias=len(radar), documentos=len(library)-len(pending), ejecuciones=len(activity),
                                  pendientes_revision=len(pending)+len(warnings), duplicados_omitidos=ndup+ddup))
    for ds, value in (('radar', radar), ('biblioteca', library), ('fuentes', sources), ('actividad', activity)):
        write(p, 'datos/' + ds + '.json', value)
    state = read(p, 'estado/estado.json', {})
    state.update(dict(ultima_ejecucion=event['id'], inventario=inv))
    write(p, 'estado/estado.json', state)
    write(p, 'dashboard/data.json', dashboard)
    write(p, history, dict(candidatos=c, resultados=output, inventario=inv, dashboard=dashboard))
    return dashboard

def project_status(p):
    c = read(p, CANDIDATES)
    return dict(plan=c['plan'] if c else None, inventario=inventory(p),
                ultima_ejecucion=read(p, 'estado/estado.json', {}).get('ultima_ejecucion'), validacion=validate_project(p))
