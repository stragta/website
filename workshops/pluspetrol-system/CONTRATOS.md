# Contratos operativos v0.3

Los ejemplos de esta página son plantillas, no datos de investigación. Todos los campos indicados son obligatorios; datos desconocidos usan `null`, nunca una fecha, ruta o huella inventada. IDs de noticias y documentos permanecen estables entre candidatos, resultados y fuentes. `id --kind noticia|documento --url URL` genera IDs deterministas por URL normalizada. IDs de búsquedas son textos no vacíos.

## estado/candidatos_investigacion.json

```json
{
  "plan": {
    "id": "run-identificador",
    "aprobado": false,
    "periodo": {"desde": "2026-10-01", "hasta": "2026-10-07"},
    "consultas": [{"id": "consulta-1", "texto": "consulta acordada según perfil"}],
    "fuentes_prioritarias": [],
    "modo_ejecucion": "secuencial",
    "herramientas": {"busqueda_web": false, "navegacion": false, "descarga": false}
  },
  "noticias": [],
  "documentos_detectados": [],
  "aprobaciones": []
}
```

`plan` crea el borrador sin buscar. El agente completa consultas, fuentes, periodo y herramientas realmente disponibles ANTES de pedir aprobación. `modo_ejecucion` acepta `secuencial` o `delegacion_real`; solo el segundo cuando hubo subagentes reales. `plan --new` archiva candidatos anteriores y abre otra ejecución. El motor conserva las propiedades existentes de configuración.

Cada candidato noticia:

```json
{
  "id": "noticia-id-estable", "seleccionado": false,
  "titulo": "Título verificado", "fuente": "Institución original",
  "url": "https://example.org/noticia", "fecha_publicacion": null,
  "fecha_actualizacion": null, "fecha_consulta": null,
  "temas": [], "extracto_factual": null,
  "motivo_relevancia": "Relación con el perfil", "advertencias": [],
  "busqueda_id": "consulta-1", "documentos_relacionados": [],
  "estado_acceso": "abierto", "contenido_leido": "leido"
}
```

Cada candidato documento y registro bibliotecario:

```json
{
  "id": "documento-id-estable", "seleccionado": false,
  "titulo": "Título verificado", "institucion": null,
  "url": "https://example.org/informe", "fecha_publicacion": null,
  "fecha_actualizacion": null, "fecha_consulta": null, "fecha_documento": null,
  "tipo_documento": null, "version": null,
  "temas": [], "motivo_relevancia": "Relación con el perfil", "advertencias": [],
  "busqueda_id": "consulta-1", "noticia_origen_id": null,
  "estado_acceso": "pendiente", "contenido_leido": "inaccesible",
  "ruta_local": null, "huella": null, "resumen": null
}
```

`estado_acceso`: `abierto|parcial|inaccesible|pendiente`.
`relevancia` es opcional: `alta|media|baja`; sin valor el dashboard usa el filtro «Sin clasificar». `motivo_relevancia` es siempre obligatorio y explica la relación con el perfil.
`contenido_leido`: `leido|parcial|inaccesible`. Parcial/inaccesible exige advertencias que expliquen el alcance o bloqueo. Inaccesible exige resumen/extracto nulo. Una referencia sin lectura permanece separada en el dashboard. La lectura solo del resumen ejecutivo se registra `parcial` y el resumen identifica ese alcance.

Fechas: texto ISO 8601 (día o timestamp) o `null`. La ventana se aplica a publicación de noticias; documentos de referencia pueden ser anteriores o posteriores, con advertencias cuando corresponda. `ruta_local` es `entrada/documentos/nombre.pdf` o `null`; `huella` es SHA-256 hex del archivo o `null` si no existe archivo. No se permite huella sin archivo. Un documento local puede usar URL nula. Noticias requieren URL HTTP(S). Relaciones apuntan a IDs de candidatos; `noticia_origen_id` puede ser nulo en búsqueda documental dirigida.

## Aprobación y selección

```sh
PYTHONPATH=src python3 -m sistema_agentico approve-plan --message 'Apruebo el plan'
PYTHONPATH=src python3 -m sistema_agentico select --ids noticia-id-estable documento-id-estable --message 'Selecciono estos dos candidatos'
```

Solo ejecutar después de la entrada explícita del usuario. Estos comandos registran `{tipo: "plan"|"seleccion", ids: ["ID"], fecha: "timestamp ISO", entrada_usuario: "texto real"}` en `aprobaciones` y cambian los bool correspondientes. No basta modificar `seleccionado` ni `aprobado` a mano. Selección aditiva: los IDs ya aprobados permanecen aprobados. Nunca se incorpora un resultado no seleccionado.

## resultados/pendientes/investigador.json y bibliotecario.json

```json
{
  "agente": "investigador",
  "ejecucion_id": "run-identificador",
  "estado": "parcial",
  "registros": [],
  "advertencias": []
}
```

Bibliotecario usa `agente: "bibliotecario"`. Estado: `completado|parcial|bloqueado`. Registros usan el candidato del rol correspondiente (se permite omitir `seleccionado`), con contenido efectivamente leído, archivo descargado y huella actualizados. URL y IDs de procedencia deben coincidir con el candidato aprobado. Puede devolver cero registros con advertencias; si hay seleccionados, debe existir salida del rol, incluso bloqueada. El Investigador guarda además ficha Markdown en `entrada/noticias`. El Bibliotecario descarga originales sin sobrescribirlos y registra la lectura parcial cuando no leyó todo.

## datos/fuentes.json

```json
{"busquedas": [], "registros": [], "relaciones": []}
```

El motor añade búsquedas `{id,texto,ejecucion_id}`, registros `{id,tipo: "noticia"|"documento",url,ruta_local,fecha_consulta,busqueda_id}` y relaciones `{busqueda_id,noticia_id,documento_id}`. Las relaciones pueden apuntar a candidatos documentales pendientes y nunca convierten una referencia en contenido analizado. La deduplicación conserva IDs canónicos y remapea vínculos al consolidar.

## Ejecución local

```sh
PYTHONPATH=src python3 -m sistema_agentico plan
PYTHONPATH=src python3 -m sistema_agentico validate
PYTHONPATH=src python3 -m sistema_agentico consolidate
PYTHONPATH=src python3 -m sistema_agentico status
python3 -m http.server 8000 --bind 127.0.0.1
```

Abrir `http://127.0.0.1:8000/dashboard/` sirviendo la raíz (necesario para enlaces a documentos). Repetir consolidate y comprobar igualdad del dashboard, radar, biblioteca, actividad e historial. Validate devuelve `{valido,errores,advertencias}`; cero resultados es válido con advertencia, nunca certifica producción ni investigación exitosa.
