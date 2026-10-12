# Sistema agéntico gerencial · v0.3 investigación

Base limpia: ocho campos de perfil vacíos/editables, entradas y resultados vacíos. No incluye noticias, documentos ni perfiles de demostración.

Abre la carpeta en ChatGPT Desktop → ChatGPT → Work → Local. Codex es alternativa técnica. Selecciona el modelo indicado por la guía y confirma herramientas disponibles. Lee AGENTS.md y CONTRATOS.md antes de investigar.

El flujo es perfil → plan → aprobación → búsqueda real → candidatos → selección → noticias y biblioteca → consolidación → dashboard → auditoría. Python usa solo biblioteca estándar para estado, validación, huellas e historial; no integra buscadores ni modelos.

Desde la raíz:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m sistema_agentico plan
# Completa el plan y espera aprobación humana antes de buscar.
PYTHONPATH=src python3 -m sistema_agentico approve-plan --message 'Apruebo el plan'
# Investiga con herramientas web y guarda candidatos con seleccionado false.
PYTHONPATH=src python3 -m sistema_agentico select --ids ID_NOTICIA ID_DOCUMENTO --message 'Selecciono estos candidatos'
# Guarda fichas, recupera documentos y produce salidas según CONTRATOS.md.
PYTHONPATH=src python3 -m sistema_agentico validate
PYTHONPATH=src python3 -m sistema_agentico consolidate
PYTHONPATH=src python3 -m sistema_agentico consolidate
python3 -m http.server 8000 --bind 127.0.0.1
```

Abre http://127.0.0.1:8000/dashboard/. Sirve la raíz para abrir enlaces a entrada/documentos. `status` inspecciona; `plan --new` inicia otra ejecución y archiva candidatos previos; `id --kind documento --url URL` genera un ID estable. Para nueva ejecución mueve las salidas previas a su historial ya registrado antes de generar nuevas, o reemplaza solo las salidas de agentes; nunca originales.

Cero resultados valida con advertencias y no significa investigación exitosa. Validación para uso local, no preparación para producción institucional.

Pruebas y bundle reproducible:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
node tests/test_dashboard.cjs
python3 build_bundle.py
```

El empaquetador rechaza datos precargados y perfiles reales, excluye caches y produce un ZIP con una sola carpeta raíz. No publica ni hace commit.
