# RobotEye

RobotEye — clon ligero de Maltego: motor de grafos (networkx) + transforms OSINT
sin API keys + interfaz de escritorio nativa (PySide6, QGraphicsView/Scene),
con estética hacker/cyberpunk (fondo tipo Tron, nodos con glow neón, tipografía
monoespaciada estilo terminal).

## Instalación (dev)

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux:   source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Uso

0. **Caja "BUSCAR"** arriba del panel lateral: escribe un valor (subcadena,
   sin importar mayúsculas) o el nombre exacto de un tipo (ej. `IP`) para
   recorrer uno a uno todos los nodos de ese tipo. Cada Intro centra la
   vista sobre el resultado y lo resalta un momento -- imprescindible en
   cuanto el grafo crece más allá de una docena de nodos (algo habitual
   ahora: una sola "Ejecutar todas" o un análisis de email pueden generar
   8-11 nodos de golpe).
1. **Proyecto → Nuevo** o añade una entidad manual desde el panel lateral
   (elige tipo, ej. `Domain`, escribe el valor, ej. `example.com`, y pulsa Añadir).
1b. **Proyecto → Importar lista...** para añadir muchas entidades de golpe
   (pega una lista, una por línea). Con "Autodetectar tipo" activado
   (por defecto), reconoce Email/URL/IP/Domain de forma inequívoca por
   patrón y usa el tipo elegido como respaldo para lo ambiguo (nombres,
   usernames...) -- nunca arriesga una clasificación incorrecta y
   silenciosa. Reusa la misma deduplicación que añadir una a una: pegar
   dos veces la misma lista no crea nodos repetidos.
2. Clic derecho sobre un nodo → aparecen las transforms aplicables a ese tipo
   de entidad (ej. sobre un `Domain`: WHOIS, subdominios crt.sh, DNS A/AAAA, MX, NS).
   Si hay más de una pasiva aplicable, arriba del todo aparece
   **`▶▶ Ejecutar todas (N)`** — lanza de golpe todas las transforms pasivas
   de ese nodo en paralelo (nunca las de reconocimiento activo, que siempre
   piden confirmación una por una). Inspirado en el icono `>>` ("Run all in
   this Set") de Maltego, documentado en su artículo oficial *The Run
   Transforms Menu*.
3. Los resultados aparecen como nodos nuevos conectados por aristas, con
   posicionamiento automático en círculo alrededor del nodo origen.
4. Clic izquierdo en un nodo → panel de detalles a la derecha.
5. **Proyecto → Guardar como JSON / SQLite** para persistir, y **Abrir** para recargar.
   Las posiciones de los nodos (muevas uno a mano o uses auto-organizar) se
   guardan junto al grafo, así que al reabrir el proyecto lo encuentras tal
   y como lo dejaste, no recolocado al azar.
5b. **Proyecto → Exportar informe (HTML/PDF)** genera un documento limpio
   y legible de toda la investigación: resumen por tipo de entidad, y cada
   nodo con sus propiedades y sus conexiones -- pensado para entregar a un
   cliente o archivar un hallazgo, no para trabajar dentro de la app. La
   recogida de datos vive separada del formato de salida
   (`core/report_generator.py::build_report_data()`), así que HTML y PDF
   comparten exactamente el mismo contenido.
5c. **Proyecto → Analizar email sospechoso (.eml)** para triaje de
   spearphishing: analiza las cabeceras de un correo que ya tienes (un
   `.eml` exportado de Outlook/Gmail/Thunderbird) y puebla el grafo de
   golpe con remitente, destinatarios, Reply-To, IP de origen real
   (extraída de la cabecera `Received` más antigua), dominio, enlaces del
   cuerpo y hash de adjuntos -- todo como tipos de entidad ya existentes,
   así que las 60 transforms de la app aplican de inmediato sobre lo que
   aparezca. Marca indicadores de suplantación verificables (Reply-To o
   Return-Path distinto del remitente, SPF/DMARC en fallo) sin arriesgar
   falsos positivos con heurísticas de nombre-vs-dominio poco fiables
   (ver la sección dedicada más abajo). Es análisis de un fichero que ya
   tienes, no acceso a ningún buzón de correo.
6. **Vista → Auto-organizar (layout de fuerzas)** aplica un spring layout
   (networkx) a todo el grafo de golpe — mucho más legible que el
   posicionamiento circular aleatorio inicial cuando el grafo crece y tiene
   muchas relaciones cruzadas. Es reproducible: el mismo grafo siempre da
   el mismo layout.

## Transforms incluidas

| Transform | Entrada | Salida | Fuente |
|---|---|---|---|
| Domain → IPs (A/AAAA) | Domain | IP | resolución DNS directa |
| Domain → MX | Domain | Domain | resolución DNS directa |
| Domain → NS | Domain | Domain | resolución DNS directa |
| Domain → SOA (email del administrador técnico) | Domain | Domain, Email | resolución DNS directa (email del admin técnico de la zona) |
| Domain → WHOIS info | Domain | Organization, Person, Email | protocolo whois (puerto 43) |
| Domain → Subdominios (crt.sh) | Domain | Domain | crt.sh (Certificate Transparency) |
| Domain → Google Dorks (sugeridos) | Domain | Dork | generación local, sin red |
| Domain → Buscar en la dark web (Ahmia, manual) | Domain | *(enriquece el propio nodo)* | generación local, sin red -- nunca consulta a Ahmia |
| Domain → Buscar documentos públicos (PDF/XLSX/DOCX) | Domain | URL | DuckDuckGo, ejecuta lo que "Google Dorks" solo sugiere |
| Ejecutar Dork (vía DuckDuckGo) | Dork | URL | DuckDuckGo HTML (scraping tolerado) |
| Email → Breaches y Pastes (XposedOrNot) | Email | Breach, Paste | XposedOrNot (gratis, sin key) |
| Phone → Análisis (país, operador, tipo) | Phone | Organization (operador) | **offline**, librería `phonenumbers` |
| Phone → Búsqueda web (páginas que lo mencionan) | Phone | URL | DuckDuckGo (búsqueda inversa pasiva) |
| Username → Perfil de GitHub | Username | URL | API pública oficial de GitHub |
| Username → Perfil de Reddit | Username | URL | API JSON pública de Reddit |
| Username → Otras redes (comprobación pasiva, verificar a mano) | Username | URL | comprobación pasiva tipo Sherlock (×8 plataformas) |
| Username → Perfil de GitLab | Username | URL | API pública oficial de GitLab |
| Domain → Snapshots archivados (Wayback Machine) | Domain | URL | Wayback Machine (CDX API) |
| Domain → Subdominios históricos (Wayback Machine) | Domain | Domain | Wayback Machine (CDX API) |
| URL → Metadatos del documento (PDF/DOCX/XLSX) | URL (PDF/DOCX/XLSX) | Person, Organization | descarga directa + extracción local (pypdf/docx/openpyxl) |
| URL → Metadatos de imagen (EXIF) | URL (JPG/JPEG/TIFF) | *(enriquece el propio nodo)* | descarga directa + extracción local (Pillow) |
| Software → CVEs conocidas (NVD) | Software | *(enriquece el propio nodo)* | services.nvd.nist.gov (gratis, sin key) |
| MACAddress → Fabricante | MACAddress | *(enriquece el propio nodo)* | api.macvendors.com (gratis, sin key) |
| IP → ASN (Team Cymru) | IP | ASN | Team Cymru (DNS público) |
| ASN → Organización (Team Cymru) | ASN | Organization | Team Cymru (mismo servicio que IP → ASN) |
| ASN → Prefijos de red (RIPEstat) | ASN | *(enriquece el propio nodo)* | RIPEstat (gratis, sin key) |
| Domain → SPF / DKIM / DMARC | Domain | *(enriquece el propio nodo)* | registros DNS TXT públicos |
| Person → Usernames probables | Person | Username | generación local, sin red |
| Person → Emails (búsqueda web) | Person | Email | DuckDuckGo + lectura de páginas públicas |
| Person → Teléfonos (búsqueda web) | Person | Phone | DuckDuckGo + lectura de páginas públicas |
| Person → LinkedIn y redes sociales (búsqueda web) | Person | URL | DuckDuckGo (LinkedIn, X, Instagram, Facebook) |
| Person → Empresa y ciudad (LinkedIn) | Person | Organization | DuckDuckGo + extracción de título/snippet |
| IP → PTR (DNS inverso) | IP | Domain | resolución DNS inversa |
| Hash → Identificar tipo | Hash | *(enriquece el propio nodo)* | generación local, sin red |
| Hash → Comprobar en Pwned Passwords | Hash (SHA-1) | *(enriquece el propio nodo)* | api.pwnedpasswords.com (k-anonimato, gratis) |
| IP → Shodan InternetDB (índice pasivo) | IP | Domain (hostnames) | internetdb.shodan.io (gratis, sin key, índice pasivo) |
| IP → Geolocalización aproximada | IP | *(enriquece el propio nodo)* | ip-api.com (gratis, sin key, HTTP only) |
| IP → RDAP (registro del bloque de red) | IP | Organization | rdap.org (bootstrap RFC 9083, reemplazo moderno de WHOIS) |
| IP → Comprobar en listas negras (DNSBL) | IP | *(enriquece el propio nodo)* | Spamhaus ZEN (DNS puro, gratis) |
| Email → Clave PGP (keys.openpgp.org) | Email | *(enriquece el propio nodo)* | keys.openpgp.org (API pública) |
| Organization → Dominio probable (búsqueda web) | Organization | Domain | búsqueda web DuckDuckGo (verificar a mano) |
| Organization → Dorks de personas y contacto | Organization | Dork | generación local, sin red |
| Organization → Personas vinculadas (LinkedIn) | Organization | Person | DuckDuckGo + extracción de nombre del título del resultado |
| Organization → Teléfonos (búsqueda web) | Organization | Phone | DuckDuckGo + lectura de páginas públicas |
| Organization → Buscar en la dark web (Ahmia, manual) | Organization | *(enriquece el propio nodo)* | generación local, sin red -- nunca consulta a Ahmia |
| Organization → Buscar documentos públicos (PDF/XLSX/DOCX) | Organization | URL | DuckDuckGo, sin restringir a un dominio conocido |
| Organization → Buscar publicaciones públicas (LinkedIn, X, Reddit) | Organization | URL | DuckDuckGo (índice ya público, nunca accede a mensajes privados) |
| Organization → Registro SEC (EDGAR) | Organization | *(enriquece el propio nodo)* | data.sec.gov (gratis, sin key -- solo empresas públicas de EEUU) |
| Organization → Comprobar en lista de sanciones OFAC (SDN) | Organization | *(enriquece el propio nodo)* | treasury.gov (gratis, sin key -- coincidencia por nombre, verificar a mano) |
| Person → Comprobar en lista de sanciones OFAC (SDN) | Person | *(enriquece el propio nodo)* | treasury.gov (gratis, sin key -- coincidencia por nombre, verificar a mano) |
| Organization → Noticias recientes (GDELT) | Organization | URL | api.gdeltproject.org (gratis, sin key, sin scraping) |
| Person → Noticias recientes (GDELT) | Person | URL | api.gdeltproject.org (gratis, sin key, sin scraping) |
| Organization → Litigios federales (CourtListener) | Organization | *(enriquece el propio nodo)* | courtlistener.com (gratis, sin key -- solo tribunales federales de EEUU) |
| Person → Litigios federales (CourtListener) | Person | *(enriquece el propio nodo)* | courtlistener.com (gratis, sin key -- solo tribunales federales de EEUU) |
| Organization → Usernames probables | Organization | Username | generación local, sin red |
| Breach → Dominio de origen | Breach | Domain | dato ya obtenido, sin red nueva |
| Paste → Enlace (si está disponible) | Paste | URL | dato ya obtenido, sin red nueva |
| URL → Dominio | URL | Domain | generación local, sin red (aplica a cualquier URL) |
| Domain → Emails (búsqueda web, estilo theHarvester) | Domain | Email | DuckDuckGo + lectura de páginas públicas (estilo theHarvester) |
| Email → Dominio | Email | Domain | generación local, sin red |
| Email → Persona probable (heurística) | Email | Person | heurística local, sin red |
| Email → Gravatar | Email | URL (cuentas enlazadas) | gravatar.com (hash SHA256, sin key) |
| Email → Username probable | Email | Username | generación local, sin red |
| Email → Buscar en la dark web (Ahmia, manual) | Email | *(enriquece el propio nodo)* | generación local, sin red -- nunca consulta a Ahmia |
| Domain → Teléfonos (búsqueda web) | Domain | Phone | DuckDuckGo + lectura de páginas públicas |
| URL → Emails y teléfonos (contenido de la página) | URL | Email, Phone | descarga directa de la página |
| URL → Seguir redirecciones (destino final) | URL | URL | resolución de redirecciones HTTP directa |

Ninguna de las 67 transforms de esta tabla requiere API key, y todas son
**OSINT pasivo**: consultan fuentes públicas de terceros o hacen cálculo
local, pero ninguna sondea ni envía tráfico directamente al objetivo (sin
escaneo de puertos, sin banner grabbing, sin tocar la infraestructura de
nadie). Todas corren en un `QThread` (`core/transform_runner.py`) para no
congelar la UI — excepto el análisis de teléfono y la generación de
usernames, que son puramente offline y no usan red en absoluto.

## Auditoría de código: bugs reales encontrados y corregidos

Ronda de auditoría sistemática de las 40 transforms, buscando específicamente
código que da resultados incorrectos o vacíos sin motivo real (no solo que
crashee). Se probó cada transform local con baterías amplias de casos límite
reales, y cada transform de red con datos que reproducen fielmente formatos
de respuesta reales, incluyendo campos ausentes/incompletos. Se encontraron
y corrigieron **9 bugs reales**:

| Bug | Dónde | Impacto |
|---|---|---|
| `URLToDomain`/`Organization → Dominio probable` extraían `"user"` en vez del dominio real | URLs con credenciales embebidas (`user:pass@host`) | Pivote roto a `Domain` |
| Cabecera `"MaltegoClone/0.1"` sin actualizar (nombre antiguo del proyecto) | `Domain → Subdominios (crt.sh)` | Riesgo de bloqueo silencioso |
| Campos WHOIS (`org`/`name`/`email`) sin `.strip()` | `Domain → WHOIS info` | Duplicados no detectados (el modelo deduplica por string exacto) |
| `applies_to()` no manejaba el fragmento de URL (`#seccion`) | `URL → Metadatos`, `URL → Emails y teléfonos` | Documentos/páginas no reconocidos correctamente |
| `KeyError` si un prefix de RIPEstat venía incompleto | `ASN → Prefijos de red` | Crash con datos reales parcialmente incompletos |
| Literal `"None"` mostrado en el panel de detalles | `IP → Geolocalización`, `Domain → WHOIS info` | Resultado confuso, no un dato "real" |
| Dominio en mayúsculas heredado de un artefacto de compresión DNS | `Email → Verificar buzón (SMTP)` | Cosmético (`smtp.GOOGLE.COM` en vez de minúsculas) |
| Candidatos de username vacíos para marcas cortas (`"H&M"` → 0 candidatos) | `Organization → Usernames probables` | Cero resultados en un caso real y común |
| Candidatos de username con tildes/eñes, inválidos en cualquier plataforma real | `Organization → Usernames probables` | Resultado inútil para encadenar |

**Limitación conocida (no bloqueante)**: `Person → Usernames probables` con
nombres que contienen la letra islandesa `ð` (eth) la elimina en vez de
transliterarla a `d` (NFKD no la descompone) -- caso raro, afecta solo a
nombres de origen islandés/feroés.

## Reconocimiento activo (apartado aparte, requiere confirmación)

| Transform | Entrada | Salida | Qué hace |
|---|---|---|---|
| Domain → Tecnologías web (estilo Wappalyzer) | Domain | Software | pide la home del dominio, detecta CMS/frameworks/servidor |
| Email → Verificar buzón (SMTP) | Email | *(enriquece el propio nodo)* | conecta al servidor de correo real (RCPT TO probing) |
| Domain → Certificado SSL | Domain, IP | Domain (vía SAN) | conecta al puerto 443 y lee el certificado TLS real |

Estas son las tres únicas transforms de todo RobotEye que **envían tráfico
directamente al objetivo** en vez de consultar a un tercero — viven
deliberadamente separadas de la tabla de arriba, en sus propios módulos
(`transforms/webtech_transforms.py`, `transforms/smtp_verify_transforms.py`),
marcadas con `requires_consent = True` en la clase base
(`core/transform_base.py`).

**Qué hace exactamente:** una petición HTTP normal a la home del dominio
(el mismo "nivel de contacto" que hace cualquier navegador al visitar una
web) y analiza cabeceras + patrones del HTML para identificar
CMS/frameworks/servidor, al estilo Wappalyzer/BuiltWith. No fuerza rutas,
no prueba credenciales, no manda payloads — pero sigue siendo tráfico
dirigido al objetivo, y esa es la línea que separa OSINT pasivo de
reconocimiento activo.

**Mecanismo de confirmación:** en el menú contextual, esta transform (y
cualquier otra que se marque `requires_consent = True` en el futuro)
aparece en una sección aparte, bajo el aviso "⚠ Reconocimiento activo
(toca el objetivo)". Al pulsarla, **antes de ejecutar nada**, aparece un
diálogo bloqueante pidiendo confirmar que tienes autorización expresa
sobre el objetivo — con "Cancelar" como botón por defecto, no el de
riesgo. Si no se confirma explícitamente, la transform no se ejecuta ni se
envía ninguna petición de red; queda registrado en el log de la app.

Para añadir una transform activa nueva en el futuro, basta con heredar de
`Transform`, poner `requires_consent = True`, y la UI se encarga del resto
automáticamente (agrupación en el menú + diálogo de confirmación) sin
tocar código de `main_window.py`.

### Sobre el análisis de teléfonos (100% offline)

Usa `phonenumbers`, el port en Python de la librería libphonenumber de
Google. No hace ninguna petición de red — toda la base de datos de rangos
numéricos, operadores y husos horarios va embebida en el propio paquete
Python. Funciona sin conexión a internet.

**Límites importantes, para no vender esto como algo que no es:**
- La "ubicación" es la zona de asignación del prefijo/rango (ciudad,
  provincia, país), **no la posición GPS real** del teléfono. Eso no existe
  como consulta pública ni de pago ni gratis; solo el operador y las
  fuerzas de seguridad con orden judicial pueden triangular un teléfono real.
- El operador que devuelve es el operador **original** al que se asignó ese
  rango. Si el número se ha portado a otra compañía (muy habitual), el dato
  puede estar desactualizado — la portabilidad no se refleja en estas bases
  de datos offline.

### Sobre las redes sociales (Username → perfiles)

**GitHub y Reddit** usan sus APIs públicas reales, así que son fiables:
el dato viene directo de la fuente, no de "adivinar" si una URL existe.

**El resto** (X, Facebook, LinkedIn, Instagram, TikTok, Pinterest, YouTube,
Telegram) no tienen API pública de consulta por username. Se usa la misma
técnica pasiva que Sherlock/Maigret: comprobar si la URL del perfil
devuelve una página real o un "no encontrado" — sin login, sin leer
contenido privado. Es una técnica de OSINT establecida, pero **no
infalible**: varias plataformas (sobre todo LinkedIn, y en menor medida
X y Facebook) muestran un muro de login a cualquier visita sin sesión
iniciada, exista o no el perfil, lo que puede dar falsos positivos o
negativos. Cada resultado lleva una propiedad `confianza` indicando qué
tan fiable es esa plataforma concreta — revisa a mano las de confianza
baja/media antes de darlas por buenas.

**`Person → Usernames probables`** genera candidatos locales (sin red) para
alimentar estas dos — son permutaciones típicas del nombre, sin verificar,
marcadas explícitamente con `origen: "generado... NO verificado"` para no
confundirlas con un hallazgo real.

### Sobre Wayback Machine

Usa la CDX API pública de web.archive.org (gratis, sin key, estable desde
hace más de una década). Dos transforms: snapshots archivados de páginas
concretas, y subdominios que el Archive ha visto alguna vez aunque ya no
resuelvan — útil para encontrar paneles viejos, ficheros borrados o
infraestructura histórica que ya no está en la web en vivo.

### Sobre metadatos de documentos (técnica FOCA)

`Domain → Google Dorks` → `Ejecutar Dork` ya genera URLs de PDFs/DOCX/XLSX
públicos; esta transform es el siguiente paso natural sobre esos
resultados. Descarga el documento (límite de 20 MB) y extrae autor, última
persona que lo modificó, empresa, software usado y fechas.

Detalle técnico: `python-docx` y `openpyxl` no exponen el campo "empresa"
en su API de alto nivel (solo viene en una parte interna del ZIP,
`docProps/app.xml`, que ninguna de las dos librerías expone), así que se
lee directamente del XML interno del documento — verificado con documentos
reales que sí lo extrae correctamente.

Sigue siendo OSINT pasivo: descargar un documento público es lo mismo que
hace un navegador al abrirlo, no se sondea ninguna infraestructura.

### Sobre IP → ASN

Usa el servicio de "whois vía DNS" de Team Cymru (más de 15 años en
producción, gratis, sin key): una consulta TXT normal a
`<ip-invertida>.origin.asn.cymru.com` da el ASN, prefijo BGP, país y
registro regional; una segunda a `AS<n>.asn.cymru.com` da el nombre de la
organización. Solo soporta IPv4 en este proyecto.

### Sobre SPF / DKIM / DMARC

Lectura de registros DNS TXT públicos — la misma naturaleza que el resto
de transforms DNS del proyecto. Útil en auditoría de postura anti-phishing
de un dominio (típico en una revisión GRC): un dominio sin SPF/DMARC, o
con una política DMARC laxa, es mucho más fácil de suplantar.

DKIM es distinto a los otros dos: no vive en una ubicación fija (el
"selector" lo elige quien configura el DNS), así que se prueban los
selectores más habituales de Google Workspace, Microsoft 365, Mailchimp y
proveedores genéricos. Si ninguno responde, no significa necesariamente
que no haya DKIM configurado — solo que no usa ninguno de los que probamos.

### Sobre la comprobación de brechas de datos y pastes (Email → Breaches y Pastes)

Se usa **XposedOrNot** (xposedornot.com) en vez de HaveIBeenPwned: desde la
v3 de su API, HIBP dejó de permitir comprobar breaches de un email de forma
gratuita — hace falta una suscripción de pago. XposedOrNot es una
alternativa genuinamente gratuita, open source y **sin API key** para el
mismo caso de uso, y de hecho da más detalle por brecha que la propia HIBP
(industria afectada, nivel de riesgo de la contraseña, descripción completa
del incidente, fecha, nº de registros expuestos...).

El mismo endpoint devuelve también, sin coste de otra petición, si el
email aparece en algún "paste" (Pastebin y similares). Su documentación
pública no publica un ejemplo completo de ese bloque, así que el parseo es
deliberadamente defensivo: no asume nombres de campo fijos, vuelca lo que
venga tal cual como propiedades — así no se pierde ni se rompe nada si el
esquema real difiere un poco de lo esperado.

El único límite es de uso razonable por IP en su tier gratuito: 2
peticiones/segundo, 25/hora, 100/día en el endpoint que usamos
(`breach-analytics`). No hace falta configurar nada — si lo superas, la
transform falla con un mensaje claro pidiendo esperar, en vez de crashear.

### Sobre la auditoría de cobertura (ningún tipo de entidad es un callejón sin salida)

Se hizo una auditoría sistemática de los 13 tipos de entidad para detectar
si a alguno le pasaba lo mismo que le pasaba a `Organization` originalmente:
generarse como salida de otras transforms pero no tener ninguna que lo
consumiera como entrada. Se encontraron y cerraron 3 huecos más:

- **`ASN`**: se generaba (`IP → ASN`) pero no se consumía. Ahora
  `ASN → Organización` y `ASN → Prefijos de red` lo aprovechan.
- **`Breach` y `Paste`**: se generaban vía XposedOrNot pero no se
  consumían. `Breach → Dominio de origen` y `Paste → Enlace` pivotan sobre
  ellos **sin gastar ninguna petición de red nueva** — solo extraen un dato
  ya obtenido y guardado como propiedad en la llamada original.
- **`URL`**: tenía una transform técnicamente registrada
  (`URLToDocumentMetadata`), pero solo se activaba para `.pdf`/`.docx`/`.xlsx`
  — la mayoría de URLs que genera el resto del proyecto (perfiles de
  GitHub/Reddit, snapshots de Wayback, resultados de dorks que no son
  documentos...) se quedaban sin ninguna acción disponible. `URL → Dominio`
  cubre el resto: extrae el host de cualquier URL para pivotar de vuelta a
  todo el ecosistema de transforms de `Domain`.

Un bug real se detectó y arregló durante esta auditoría: `entity.value.upper().lstrip("AS")`
en `asn_transforms.py` — `str.lstrip()` en Python trata su argumento como un
**conjunto de caracteres** a quitar, no como un prefijo literal. Con un valor
como `"ASN13335"` esto daba `"N13335"` en vez de `"13335"`. Se sustituyó por
extracción de dígitos vía regex (`_extract_asn_number()`), robusta frente a
cualquier formato de entrada.

### Sobre la ronda de transforms inspirada en el catálogo real de Maltego

Se documentó el catálogo público de Maltego Standard Transforms (CTAS) para
identificar huecos concretos en la cadena de investigación de una
`Organization`, y se replicaron con fuentes gratuitas sin key en vez de
Bing Search API (que Maltego sí usa de pago para varias de estas):

- **`Domain → SOA`**: el registro SOA de cualquier dominio incluye el email
  del administrador técnico de la zona DNS en el campo `rname` (con un
  formato heredado de los 80: el primer punto hace de arroba). Probado con
  DNS real: encontró `awsdns-hostmaster@amazon.com` en un dominio alojado
  en Route53. Equivalente a la transform `To DNS Name - SOA` de Maltego.
- **`Domain → WHOIS info` ampliada**: ahora también extrae el teléfono del
  registrante cuando el WHOIS lo publica (el nombre del campo varía según
  el TLD: `registrant_phone`, `phone`, `admin_phone`... se prueban en orden).
  Equivalente a `To Phone numbers [From whois info]`.
- **`Domain → Teléfonos (búsqueda web)`**: mismo patrón que `Domain → Emails`,
  pero para teléfonos — usa `phonenumbers.PhoneNumberMatcher` (ya dependencia
  del proyecto) en vez de una regex casera, mucho más fiable reconociendo
  números reales de distintas regiones en texto libre. Equivalente a
  `To Phone Numbers [using Search Engine]`.
- **`URL → Emails y teléfonos`**: el equivalente genérico a "Found on this
  web page" de Maltego — aplica a *cualquier* URL ya en el grafo (perfil de
  GitHub, snapshot de Wayback, resultado de un dork...), no solo a las
  páginas que auto-descubre el harvesting de `Domain`.
- **`Email → Dominio`** y **`Email → Persona probable`**: cierran el bucle
  de vuelta. Con tantas fuentes generando emails ahora (WHOIS, SOA,
  harvesting, pastes...), hacía falta poder pivotar de un `Email` de vuelta
  a `Domain`, y extraer un nombre candidato del propio formato del email
  (`nombre.apellido@...`) — equivalentes a `EmailAddress → Domain [DNS]` y
  `EmailAddress → Person [Parse separator]`.

Con esto, una investigación que empieza con solo el nombre de una empresa
(`Organization`) ahora puede llegar, sin salir de transforms gratuitas y
sin key, hasta personas y teléfonos concretos: `Organization → Domain →
{WHOIS, SOA, Emails, Teléfonos} → Email → {Domain, Persona probable,
Breaches, PGP, Verificar buzón}`.

### Sobre el registro de actividad exportable

Cuarta y última de las cuatro mejoras de flujo de trabajo. Encaja bien
con que ya existen transforms activas con diálogo de consentimiento
(`Certificado SSL`, `Tecnologías web`, `Verificar buzón`): antes, en
cuanto se cerraba la app, se perdía toda constancia de qué se había
ejecutado, contra qué objetivo y cuándo -- el panel "LOG" era puramente
visual, sin nada detrás que sobreviviera a cerrar la ventana.

Cada llamada a `MainWindow.log()` ahora alimenta también una lista
estructurada (`_activity_log`, con fecha/hora real y el mensaje) además
del texto con formato que ya se veía en el panel -- ningún cambio en lo
que el usuario ve, solo un rastro paralelo que antes no existía.
`Proyecto → Exportar registro de actividad...` lo vuelca a un `.txt`
plano, justo al lado de `Exportar informe (HTML/PDF)` en el menú (se
reordenó a propósito para que quedaran agrupados) -- útil para justificar
metodología en un informe de pentest, o simplemente para no perder
constancia de qué se comprobó y cuándo.

`core/report_generator.py` sigue sin ninguna dependencia de Qt a
propósito -- el registro vive en `MainWindow` (estado de sesión de la
ventana), así que se mantiene como una exportación independiente en vez
de inyectarse dentro de ese módulo, que es deliberadamente puro.

### Sobre las notas manuales del usuario

Tercera de las cuatro mejoras de flujo de trabajo. Todo lo que hay en las
propiedades de un nodo lo escriben las transforms automáticamente -- no
había ningún sitio donde el propio analista anotara su criterio:
"confirmado a mano", "esto parece un falso positivo", "pendiente de
verificar con el cliente". En investigación real, el juicio del analista
es tan importante como el dato en bruto.

`Entity.user_note: str` es un campo propio de la dataclass, deliberadamente
**fuera** de `properties` -- así ninguna transform puede pisarlo por
accidente al hacer `properties.update(...)`, ni falta comprobar caso a
caso si una clave concreta está a salvo. Persiste en JSON y SQLite (con
compatibilidad hacia atrás: un proyecto guardado antes de este campo
carga igual, con nota vacía por defecto, en vez de fallar por la columna
que falta). Aparece también en `Exportar informe` (HTML y PDF), con su
propio estilo visual distinto de las propiedades automáticas.

Guardado explícito con un botón, no automático al escribir -- cambiar de
nodo seleccionado a mitad de una frase sin guardar no debe arriesgar
escribir la nota en la entidad equivocada.

### Sobre litigios federales: el cuarto frente cerrado (CourtListener)

A diferencia de patentes/marcas, este sí encajaba. PACER (el sistema
oficial de EEUU) cobra ~0,10 $/página por cada documento consultado, e
incluso para buscar exige cuenta con tarjeta registrada -- descartado
por el mismo principio de siempre. CourtListener (Free Law Project, un
proyecto sin ánimo de lucro que empezó como una clínica de Stanford en
2010) mantiene RECAP, un archivo de documentos de PACER donados
públicamente por otros usuarios -- sigue sin ser 100% completo frente al
PACER real, pero es genuinamente gratuito y con cobertura considerable
(cientos de millones de elementos).

Verificación que hizo falta antes de dar la fuente por buena: la propia
documentación oficial de CourtListener es ambigua en un punto --
describe límites concretos ("5 peticiones/minuto, 50/hora, 125/día")
solo para usuarios *autenticados*, sin aclarar directamente el límite
sin autenticar. Se cruzó con dos fuentes técnicas independientes más
recientes que sí lo precisan: **5.000 peticiones/día sin key**, subiendo
a 5.000/hora con una key gratuita opcional -- de sobra para el uso de
RobotEye, y sin exigir que el usuario gestione nada.

`Organization/Person → Litigios federales (CourtListener)` busca el
nombre como parte exacta del caso (`caseName:"nombre"`, más preciso que
texto libre) contra `type=d` (expedientes sin metadatos de cada
documento -- más ligero, justo lo que hace falta para un resumen).

> **Limitación honesta**: cubre únicamente tribunales federales de
> EEUU, nunca estatales ni de otros países, y la cobertura de RECAP
> depende de qué documentos han donado otros usuarios de PACER al
> archivo público -- una ausencia de resultados no es prueba de que no
> haya litigios, solo de que no hay ninguno en RECAP con ese nombre
> exacto como parte del caso.

### Investigado y descartado: patentes y marcas registradas (USPTO)

A diferencia de los tres frentes anteriores, este se investigó a fondo y
**no se implementó** -- se documenta aquí para que quien retome esto en
el futuro no repita la misma investigación desde cero.

Se comprobaron los tres caminos relevantes de la USPTO:

- **PatentsView** (búsqueda de patentes): su documentación oficial dice
  explícitamente *"The new version of the API requires an API key, or
  all of your requests will be rejected"*. Varios listados de terceros
  afirman "sin key" -- es marketing de wrappers que gestionan su propia
  key internamente, el mismo tipo de ruido que ya se descartó con la
  Consolidated Screening List de trade.gov.
- **TSDR** (estado y documentos de marcas registradas): la propia USPTO
  lo dice sin ambigüedad -- *"You must register for an API key in order
  to use the TSDR APIs"*, desde octubre de 2020.
- **El buscador de marcas más nuevo** (`tmsearch.uspto.gov`) no tiene
  ninguna API pública documentada -- es una aplicación web en
  JavaScript pensada para uso humano interactivo. Los scrapers de
  terceros que afirman "sin key" lo consiguen suplantando huellas TLS de
  navegadores reales para evadir la detección de bot -- no es scraping
  tolerado tipo DuckDuckGo, es evasión activa de detección contra un
  sistema sin ningún contrato de acceso programático.

Los tres caminos rompen el mismo principio que se ha mantenido en todo
el proyecto: cero configuración para quien usa RobotEye, y ninguna
técnica de evasión activa de detección de bot. Se deja como limitación
conocida en vez de forzar un encaje que exigiría o bien pedirle al
usuario que gestione su propia API key (algo que ninguna otra transform
del proyecto exige), o bien construir un scraper que suplanta huellas de
navegador -- ninguna de las dos encaja con el resto de RobotEye.

### Sobre noticias/prensa: el tercer frente, y un robots.txt que dice que no

Se investigaron dos caminos antes de escribir código. El RSS de Google
News (`news.google.com/rss/search`) es técnicamente trivial -- sin key,
sin autenticación, funciona desde hace años -- pero se comprobó su
robots.txt real antes de construir nada, siguiendo la misma disciplina
que ya se aplicó con Ahmia. El resultado:

```
User-agent: *
Disallow: /
Allow: /$
Allow: /home$  Allow: /topics/  Allow: /stories/  ...
```

`/rss/search` **no está** en la lista corta de excepciones permitidas —
está prohibido por el propio robots.txt, bajo el `Disallow: /` general.
Y hay algo más: ese mismo fichero incluye una entrada explícita que
bloquea a los rastreadores de Anthropic (`anthropic-ai`, `ClaudeBot`,
`Claude-Web`) en todo el dominio. Mismo criterio que con Ahmia: si el
robots.txt dice que no, no se construye un scraper contra eso, por
trivial que sea saltárselo -- descartado.

GDELT (Global Database of Events, Language, and Tone) sí encajaba: un
proyecto financiado académicamente, con una API pública **diseñada
explícitamente** para búsqueda programática de noticias (no un canal
lateral tolerado) -- monitoriza medios de todo el mundo en 65+ idiomas,
traducidos automáticamente al inglés, sin key, con una cortesía de uso
de 1 petición cada 5 segundos por IP.

> **Detalle de robustez documentado por el propio GDELT, verificado
> antes de dar el código por bueno**: ante una consulta rara o un
> problema temporal del servicio, la API a veces responde con texto
> plano (o vacío) en vez de JSON válido, incluso con código 200 — el
> parseo de la respuesta se protege explícitamente contra esto en vez de
> asumir que un status 200 garantiza un `resp.json()` que funciona.

`Organization/Person → Noticias recientes (GDELT)` comparten la misma
función de búsqueda (nombre entre comillas, ordenado por fecha
descendente, ventana de un mes), y generan una entidad `URL` por cada
noticia encontrada -- que ya encadena solo con las transforms de `URL`
existentes (`Seguir redirecciones`, `Emails y teléfonos`), verificado de
extremo a extremo.

### Sobre el cribado de sanciones OFAC: el segundo frente de "corporate intelligence"

Continuación directa del hueco anterior. Se investigaron dos caminos
antes de escribir código: la Consolidated Screening List de trade.gov
(la opción "oficial" más completa, junta 11 listas de EEUU en una sola
API) exige **registrarse para conseguir una API key gratuita** -- se
descartó, porque rompe el patrón de cero configuración que mantiene el
resto de la app (ninguna otra transform le pide al usuario que gestione
una cuenta o una clave). El fichero CSV crudo de la lista SDN (Nacionales
Especialmente Designados) que publica directamente el Tesoro de EEUU no
exige nada de eso: se descarga sin autenticación.

Detalle real de formato que hubo que verificar antes de escribir el
parser: el fichero **no trae fila de cabecera**, así que las 12 columnas
se declaran a mano en el orden documentado por OFAC, y los campos vacíos
vienen marcados con el literal `-0-` en vez de una cadena vacía -- hay
que traducirlo explícitamente o acaba filtrándose tal cual al panel de
detalles, el mismo tipo de literal-sin-sentido que ya se evitó con
WHOIS/geolocalización en rondas anteriores de este proyecto.

`Organization/Person → Comprobar en lista de sanciones OFAC (SDN)`
comparten la misma función de búsqueda (el fichero mezcla personas,
empresas, barcos y aeronaves en una sola lista), y la misma caché a
nivel de módulo que ya se usó para el fichero de tickers de la SEC.

> **El aviso más importante de toda esta funcionalidad**: una
> coincidencia de nombre nunca es una prueba de identidad -- nombres
> comunes, transliteraciones distintas del mismo nombre, y homónimos
> hacen que esto sea, en el mejor de los casos, una pista fuerte que hay
> que verificar a mano con más datos (fecha de nacimiento, nacionalidad,
> documento), nunca una confirmación automática. A diferencia de otras
> transforms, "sin coincidencias" aquí no es un error -- es el resultado
> más común y esperable, ya que la inmensa mayoría de organizaciones y
> personas no están sancionadas.

### Sobre el registro SEC (EDGAR): el primer hueco real de "corporate intelligence"

Al revisar con qué frentes de investigación corporativa cuenta RobotEye
hoy, el hueco más claro era la ausencia de cualquier fuente de **registro
mercantil oficial** -- todo lo que había hasta ahora sobre una
`Organization` venía de heurísticas de búsqueda (dominio probable,
personas vinculadas), nunca de un registro público autoritativo.

Se investigaron dos fuentes antes de escribir código. OpenCorporates,
la opción más obvia por cobertura (200M+ empresas, 140+ jurisdicciones),
**eliminó su tier gratuito en 2026** -- ahora exige un plan de pago desde
varios miles de euros al año, incompatible con el principio de "sin
herramientas de pago" del proyecto. SEC EDGAR (la Comisión de Bolsa y
Valores de EEUU) sigue siendo 100% pública y gratuita: sin API key, solo
exige una cabecera `User-Agent` identificable y respetar 10
peticiones/segundo.

`Organization → Registro SEC (EDGAR)` busca el CIK (el identificador
único que la SEC asigna a cada declarante) por nombre en tres pasadas de
menos a más laxas -- coincidencia exacta primero, luego "el título
empieza por el nombre buscado" (para que "Apple" encuentre "Apple
Inc."), y solo como último recurso una subcadena cualquiera -- y trae la
razón social oficial, el código SIC de industria, el estado de
incorporación, tickers/mercados, y los últimos ingresos y beneficio neto
de su 10-K más reciente. El fichero de tickers (varios MB) se cachea a
nivel de módulo para no volver a descargarlo en cada nodo `Organization`
de la misma sesión.

> **Limitación honesta, no un rodeo**: SEC EDGAR solo cubre empresas que
> declaran ante la SEC de EEUU -- en la práctica, empresas públicas
> estadounidenses (o extranjeras que cotizan en bolsas de EEUU). No cubre
> empresas privadas ni empresas públicas de otras jurisdicciones. Ese
> hueco sigue abierto, y hoy no hay ninguna fuente gratuita equivalente
> para cubrirlo -- se documenta como limitación conocida en vez de
> pretender una cobertura que la herramienta no tiene.

### Sobre la confirmación antes de borrar

Segunda de las cuatro mejoras de flujo de trabajo identificadas al
revisar qué faltaba con la cobertura de datos ya amplia. Borrar un nodo
con muchas conexiones (fruto de horas de investigación) era irreversible
y no pedía confirmación -- un clic accidental y se perdía sin aviso.

`GraphModel.degree()` reutiliza `networkx.DiGraph.degree()` (cuenta
conexiones entrantes y salientes juntas) para que el aviso sea
**informativo, no genérico**: un nodo aislado se sigue borrando sin
preguntar (no tiene nada que perder salvo a sí mismo), pero uno con
conexiones muestra cuántas exactamente antes de confirmarlo. El botón por
defecto es "No" a propósito -- un Enter accidental en el diálogo no debe
borrar nada.

La lógica de borrado real (`_delete_entity_confirmed`) queda separada de
la confirmación, igual que ya se hizo con la importación masiva y la
búsqueda -- se puede testear sin simular clics en un `QMessageBox`.

### Sobre la búsqueda en el lienzo

Repaso de qué faltaba ahora que la cobertura de datos ya es amplia: no
más fuentes, sino flujo de trabajo. Con transforms que generan 8-11 nodos
de golpe (`Ejecutar todas`, el análisis de email), un grafo real puede
crecer muy rápido -- encontrar un nodo concreto a ojo deja de ser viable
pronto.

Una única caja de texto con dos modos: si el texto coincide EXACTAMENTE
(sin importar mayúsculas) con un tipo de entidad válido, filtra por tipo
(escribir `IP` recorre uno a uno todos los nodos IP); si no, busca como
subcadena en el valor de cualquier entidad. Cada Intro centra la vista
(`QGraphicsView.centerOn()`) sobre el resultado y lo resalta agrandando y
aclarando temporalmente su glow neón existente, revirtiendo solo tras un
tiempo -- sin depender de ningún elemento visual nuevo, reutilizando lo
que cada nodo ya tenía.

**Bug real encontrado, pero en mi propio test, no en el código de
producción**: al verificar que dos `highlight()` seguidos no se pisan
(el segundo debe cancelar el timer del primero), monté mal la aritmética
de tiempos de mi primera prueba -- comprobé el resultado en un instante
ya pasado el momento en que el SEGUNDO timer disparaba legítimamente, así
que el test fallaba por un error de cálculo mío, no porque el código
estuviera mal. Corregido el test (comprobar en el instante intermedio
correcto: después de cuándo dispararía el primer timer si no se hubiera
cancelado, pero antes de cuándo dispara el segundo) y reconfirmado el
mismo comportamiento con la aritmética correcta.

Lección: un test que falla no significa automáticamente que el código de
producción esté mal -- hace falta releer la lógica del propio test con
los mismos ojos críticos que el código que verifica.

### Sobre documentos y publicaciones públicas: ejecutar el dork, no solo generarlo

Continuación directa de la conversación sobre "documentos, mensajes y
demás como hace Maltego": se distinguió qué encajaba de verdad. Los
documentos ya tenían base (`Domain → Google Dorks` sugiere `filetype:pdf`
entre otros, `URL → Metadatos del documento` extrae autor/fecha de uno ya
encontrado) pero faltaba el paso intermedio -- ejecutar la búsqueda, no
solo generarla para copiar y pegar a mano. Las publicaciones **públicas**
(no mensajes privados, que nunca se planteó) tienen exactamente el mismo
hueco.

- **`Domain/Organization → Buscar documentos públicos`**: reutiliza
  literalmente los mismos tres filetypes que ya genera
  `Domain → Google Dorks` (PDF, XLSX, DOCX) -- sin inventar cobertura
  nueva, solo automatizando la ejecución. Combina `site:dominio.com` con
  los tres `filetype:` unidos por `OR` en una única petición (verificado
  que DuckDuckGo soporta esta sintaxis antes de escribir el código, con
  el matiz honesto de que su propia documentación admite que la sintaxis
  avanzada "no opera al 100% en todas las consultas" -- de ahí que un
  resultado vacío se explique como lo más habitual, no como un fallo).
  Una única petición a propósito, no una por filetype: encadenar varias
  peticiones seguidas dentro de una misma transform habría creado
  exactamente el patrón de ráfaga que el escalonado de "Ejecutar todas"
  (ver más abajo) intenta evitar.
- **`Organization → Buscar publicaciones públicas`**: misma técnica que
  `Person → LinkedIn y redes sociales` ya usaba -- consulta el índice ya
  público de DuckDuckGo sobre `linkedin.com/posts`, `x.com`, `twitter.com`
  y `reddit.com`, nunca visita la red social directamente ni accede a
  nada privado.

Verificado que el resultado de la búsqueda de documentos encadena solo
con `URL → Metadatos del documento` (ya existía, sin tocarla) -- el
objetivo completo: de un dominio a los metadatos de un documento
encontrado, en dos clics en vez de copiar un dork a mano. Las 3 nuevas
llevan `uses_ddg = True`, así que participan en el escalonado ya
existente de "Ejecutar todas" (§ más abajo) igual que el resto.

### Sobre "Analizar email sospechoso": triaje de spearphishing, no acceso a buzones

Petición inicial ambigua: "acceder a documentos, mensajes y demás como
hace Maltego". Se distinguió con cuidado entre dos cosas muy distintas
antes de escribir código: acceder a mensajes **privados** (bandeja de
entrada, DMs) de alguien sin autorización es intrusión informática, y no
se planteó en ningún momento. Analizar un correo que **ya tienes** (te lo
mandaron a ti, o te lo remitió un cliente para investigarlo) es análisis
forense estándar -- exactamente lo que se enseña en cualquier máster de
ciberseguridad.

`core/email_analyzer.py` usa únicamente el módulo `email` de la librería
estándar de Python (sin dependencias nuevas). Extrae remitente,
destinatarios, Reply-To, resultado de SPF/DKIM/DMARC (de la cabecera
`Authentication-Results`, no calculado por RobotEye), la IP de origen
real (de la cabecera `Received` más antigua -- cada salto de correo
antepone la suya, así que la última del fichero es la más cercana al
origen), enlaces del cuerpo, y hash de adjuntos. Todo se puebla como
tipos de entidad que **ya existían** (Email, Domain, IP, URL, Hash), así
que las 60 transforms de la app aplican de inmediato -- verificado
encadenando una comprobación DNS real (listas negras) sobre la IP
extraída de un correo de prueba, de principio a fin.

**Dos falsos positivos reales encontrados y corregidos** al probar la
detección de suplantación con casos que deberían dar negativo:

- Un nombre mostrado con palabras añadidas (`"Banco Ejemplo - Seguridad"`)
  se marcaba como sospechoso pese a coincidir de verdad con su dominio
  (`banco-ejemplo.com`) -- la comparación exigía que el nombre completo
  fuera substring literal del dominio, y el añadido `"- Seguridad"` (muy
  habitual también en remitentes legítimos) rompía esa comparación.
- Más grave: el nombre de una **persona** (`"Ana Lopez"`) enviando desde
  el dominio de su propia empresa se marcaba como sospechoso, cuando ese
  es el patrón normal y mayoritario de cualquier correo corporativo -- el
  nombre de un empleado no tiene por qué guardar ninguna relación léxica
  con el dominio de la empresa.

Distinguir de forma fiable "nombre de marca suplantada" de "nombre de
persona normal" no es viable con una heurística simple sin arriesgar
avisar de spoofing en la mayoría de correos legítimos que pasan por la
herramienta. Se **eliminó** esa comprobación por completo en vez de
intentar remendarla -- mejor 4 indicadores sólidos y 100% verificables
(Reply-To, Return-Path, SPF, DMARC) que un quinto que grita lobo. El
nombre y el dominio se muestran igualmente como propiedades del nodo,
para que el usuario lo valore él mismo.

### Sobre las 3 últimas incorporaciones: SSL, CVE y MAC

A partir de una revisión de qué tipos de nodo y transforms seguían
faltando (evitando relleno artificial), se identificaron y cerraron tres
huecos reales:

- **`Domain/IP → Certificado SSL`** (activa): conecta al puerto 443 y lee
  el certificado TLS del objetivo, igual que hace cualquier navegador al
  abrir una web con HTTPS. El campo más valioso es el SAN (Subject
  Alternative Names): un certificado moderno declara ahí todos los
  nombres para los que es válido, a veces revelando subdominios que
  `Domain → Subdominios (crt.sh)` no capturó (si el certificado se
  renovó después de que los logs de Certificate Transparency lo
  indexaran). **Bug de diseño real encontrado antes de escribir el resto
  del código**: para leer un certificado autofirmado o con nombre no
  coincidente hace falta conectar con `verify_mode = ssl.CERT_NONE`, pero
  con `CERT_NONE` el método de alto nivel `getpeercert()` de Python
  devuelve un diccionario **vacío** aunque la conexión funcione
  perfectamente -- se comprobó esto en directo contra un dominio real
  antes de dar nada por hecho. Solución: pedir el certificado en binario
  y parsearlo con la librería `cryptography`. Verificado con un servidor
  TLS local propio (certificado con 4 SANs, incluido uno simulando un
  subdominio "oculto") para confirmar el pipeline completo con una
  conexión TLS real, no mockeada.
- **`Software → CVEs conocidas (NVD)`**: cierra el círculo con
  `Domain → Tecnologías web`, que hasta ahora solo guardaba las
  tecnologías detectadas como texto plano, sin poder pivotar más allá.
  Se añadió el tipo de entidad `Software`, y esa transform ahora además
  genera un nodo por cada tecnología detectada (cambio aditivo,
  verificado que no rompe el comportamiento anterior). Aviso de precisión
  importante y documentado en el propio módulo: el detector de
  tecnologías identifica presencia, no versión exacta, así que la
  búsqueda de CVEs es por palabra clave (cobertura amplia) y no por CPE
  exacto (precisión por versión) -- cada resultado incluye su CVSS para
  que el usuario descarte a mano lo que no aplique.
- **`MACAddress → Fabricante`**: nuevo tipo de entidad + consulta a
  `api.macvendors.com` (gratis, sin key) para identificar el fabricante a
  partir del OUI. Se descartó mantener una copia local de la base de
  datos del IEEE (58.000+ entradas solo en el registro MA-L) por quedar
  desactualizada sin mantenimiento activo -- más honesto depender de una
  fuente que sí se mantiene al día.

### Sobre IMINT: metadatos EXIF de imágenes (URL → Metadatos de imagen)

A partir de un esquema de disciplinas de inteligencia (OSINT, HUMINT,
IMINT, análisis estructurado, verificación), se evaluó cuál de esas
categorías encajaba de verdad con la arquitectura de este proyecto antes
de implementar nada. La conclusión honesta: HUMINT no es automatizable
(es inteligencia que se obtiene hablando con personas), el análisis
estructurado es una metodología de pensamiento para humanos, no una
fuente de datos -- ninguna de las dos encaja con el modelo de "nodo → clic
derecho → más nodos". IMINT sí encaja perfectamente, y ya estaba anotada
en el roadmap de este README desde hace tiempo sin haberse implementado
nunca: `URL → Metadatos de imagen (EXIF)`.

**Qué hace**: extrae los metadatos EXIF incrustados en fotografías (JPEG,
TIFF) -- coordenadas GPS de dónde se tomó la foto, convertidas de
grados/minutos/segundos a decimal con un enlace de Google Maps ya
preparado, fabricante y modelo de cámara/móvil, y fecha de captura. Es la
técnica de geolocalización por fotografía más clásica del periodismo de
investigación y el OSINT: mucha gente sube fotos sin saber que llevan la
ubicación exacta incrustada.

**Verificado con datos reales, no solo mockeados**: se construyó una
imagen JPEG con EXIF+GPS real usando Pillow (coordenadas de la Torre
Eiffel en formato DMS, tal y como las escribe una cámara de verdad) y se
confirmó que las coordenadas decimales calculadas por la transform
coinciden con la ubicación real (48.858192, 2.294467).

**Cobertura honesta, documentada en el propio módulo**: solo se ofrece
para JPEG/TIFF (los formatos que llevan EXIF de forma fiable -- PNG/WEBP
casi nunca lo llevan, así que no se ofrece para ellos y no se promete una
comprobación que en la práctica case siempre vacía). Y un aviso importante
para el usuario: **las redes sociales grandes (Facebook, Instagram,
Twitter/X, WhatsApp) eliminan el EXIF, incluido el GPS, al recomprimir las
fotos que subes** -- por eso esta transform rara vez encuentra GPS en una
foto bajada de esas plataformas, pero sí es habitual encontrarlo en fotos
alojadas directamente en la web propia de alguien o en foros que no
recomprimen.

### Sobre Google, Tor y por qué solo una de las dos ideas se implementó

Se planteó añadir Google y Tor como fuentes adicionales, además de
DuckDuckGo. Investigado a fondo antes de escribir una línea de código,
la conclusión fue distinta para cada uno:

- **Google**: descartado. En 2026 requiere proxies residenciales de pago
  y sortear reCAPTCHA v3 (una puntuación de comportamiento invisible que
  no se "resuelve", solo se evita con infraestructura de pago) -- rompe
  el principio de "sin herramientas de pago" mantenido en todo el
  proyecto. La API oficial de Google Custom Search existe, pero exige
  API key y tiene un tope gratuito de 100 consultas/día.
- **Tor como proxy para esquivar bloqueos**: descartado. Hay evidencia
  documentada de que DuckDuckGo **detecta y bloquea explícitamente** el
  tráfico que sale de nodos de salida de Tor -- las IPs de salida de Tor
  están en listas de reputación por historial de abuso. Enrutar por Tor
  no ayudaría a evitar el bloqueo de la sección anterior: podría
  empeorarlo.
- **Tor para buscar en la dark web (`.onion`)**: sí es una capacidad
  genuinamente distinta y valiosa (comprobar si un dominio/empresa/email
  aparece mencionado en foros o mercados de la dark web es una práctica
  de threat-intel estándar). Ahmia (ahmia.fi) es el índice recomendado
  para esto -- filtra activamente contenido ilegal a nivel de índice, a
  diferencia de alternativas más permisivas como Torch o Haystak.

**Pero el propio robots.txt de Ahmia prohíbe explícitamente el acceso
automatizado a su búsqueda** -- comprobado directamente antes de escribir
código: una petición de prueba a `ahmia.fi/search/` fue rechazada citando
su `Disallow`. Dado que este proyecto ha respetado sistemáticamente las
políticas de cada fuente (LinkedIn, crt.sh, DuckDuckGo...), la decisión
fue no construir un scraper contra un `Disallow` explícito, aunque fuera
técnicamente trivial saltárselo cambiando cabeceras. Las alternativas que
sí toleran scraping automatizado (Torch, Haystak) son peores precisamente
en lo que hacía atractiva a Ahmia (no filtran contenido ilegal), así que
cambiar de fuente por conveniencia técnica habría sido un paso atrás.

**Solución adoptada: generar el enlace, nunca ejecutarlo.**
`Domain/Organization/Email → Buscar en la dark web (Ahmia, manual)` no
hace ninguna petición de red -- construye la URL de búsqueda
(`https://ahmia.fi/search/?q=...`) y la deja como propiedad del propio
nodo, lista para que el usuario la abra él mismo en su navegador cuando
quiera. Mismo principio que `Organization → Dorks de personas y
contacto`, pero llevado un paso más allá: ni siquiera se genera como
entidad `URL`, precisamente para que ninguna otra transform del proyecto
(`URL → Seguir redirecciones`, `URL → Emails y teléfonos`) pueda acabar
consultando ahmia.fi de forma automática sin que el usuario lo pida. Se
verificó explícitamente con un test que intercepta `requests.get/post/head`
que estas tres transforms hacen **cero** peticiones de red.

### Sobre el bloqueo anti-bot de DuckDuckGo ("ayer funcionaba, hoy no")

Si de repente varias búsquedas basadas en DuckDuckGo (dorking, harvesting
de email/teléfono, `Organization → Dominio probable`/`Personas
vinculadas`, todas las de `Person`...) dejan de dar resultados de un día
para otro sin haber cambiado nada, **casi seguro no es un bug**: es el
sistema de detección de anomalías de DuckDuckGo (`DDG.deep.anomalyDetectionBlock`),
un mecanismo público y bien documentado que puede bloquear una IP en
cuestión de minutos si detecta un patrón de tráfico automatizado (por
ejemplo, probar muchas transforms seguidas en poco tiempo).

RobotEye ahora detecta esto explícitamente (`is_ddg_blocked()` en
`dorking_transforms.py`, comprobado en las 10 transforms que consultan
DuckDuckGo directamente) y avisa con un mensaje claro en vez de un
ambiguo "no se encontraron resultados" que parecería decir que el dato no
existe. El bloqueo suele levantarse solo tras un tiempo sin hacer
búsquedas seguidas -- no hay nada que "arreglar" salvo esperar.

### Sobre el escalonado de "Ejecutar todas" (prevención, no solo detección)

Construyendo sobre lo anterior: detectar el bloqueo después de que ocurre
está bien, pero reducir la probabilidad de que ocurra es mejor. `Ejecutar
todas` lanzaba antes todas las transforms pasivas de golpe, en el mismo
instante -- si varias de ellas consultaban DuckDuckGo (algo habitual en
`Domain`, `Organization` y `Person`), eso generaba exactamente el patrón
de ráfaga de tráfico automatizado que dispara la detección de anomalías.

Las transforms que consultan DuckDuckGo de verdad llevan la marca
`uses_ddg = True` (11 en total -- **explícita, no detectada por
inspección de código**: intentarlo con AST tiene un punto ciego real,
varias de ellas comparten un helper de red compartido en vez de llamar a
`requests.get` directamente en su propio `run()`, así que un análisis
automático de "¿quién llama a la API de DDG?" se deja alguna sin marcar).
`run_all_passive_transforms()` ahora escalona su lanzamiento
(`DDG_STAGGER_MS = 700`, configurable) mientras el resto se sigue
lanzando al instante -- no hay motivo para ralentizar transforms que no
comparten ese riesgo.

**Bug real encontrado al verificar esta funcionalidad, no al construirla
desde cero**: el atributo `uses_ddg` y la lógica de escalonado ya
existían en el código, pero usaban `QTimer` sin importarlo -- crasheaba
con `NameError` en cuanto "Ejecutar todas" tocaba cualquier `Domain` (que
tiene 2 transforms con `uses_ddg`). Confirmado el crash de verdad antes
de arreglarlo, corregido el import, y verificado con cronometraje real
(no solo "no lanza excepción"): las transforms sin DDG se disparan en el
mismo instante, la primera de DDG a los 0ms, la segunda a los ~700ms. El
test de regresión escrito para esto confirma explícitamente que detecta
el bug exacto: revertir el import hace que el test falle con el mismo
`NameError`, no silenciosamente.

### Sobre la revisión de cobertura final: 9 transforms nuevas en 7 tipos de entidad

Repaso sistemático de los 13 tipos de entidad para ver cuáles se habían
quedado cortos de transforms razonables (sin inventar rellenos
artificiales). Se investigó primero el esquema exacto de cada API nueva
antes de escribir código contra ella, para no mockear con datos
inventados en los tests. Nueve huecos reales cerrados:

- **`IP → RDAP`**: el equivalente de `Domain → WHOIS info` para IPs. RDAP
  (RFC 9083) es el reemplazo moderno y estandarizado de WHOIS -- responde
  en JSON, y `rdap.org` hace de "bootstrap": redirige automáticamente al
  RIR correcto (ARIN/RIPE/APNIC/LACNIC/AFRINIC) sin tener que saber de
  antemano cuál consultar. Los datos de contacto vienen en formato vCard
  (RFC 6350) dentro de cada entidad -- hay que extraer la propiedad `fn`
  del array, no es un campo plano.
- **`IP → Comprobar en listas negras (DNSBL)`**: consulta Spamhaus ZEN,
  puro DNS (una resolución A contra un nombre especial), gratis, sin key.
  Detalle importante: el rango de respuesta `127.255.255.*` es una señal
  de **error** de la propia consulta (resolutor abierto, volumen
  excesivo), no un listado real -- hay que distinguirlo explícitamente
  para no dar un falso positivo de "está en una lista negra".
- **`Email → Gravatar`**: técnica OSINT clásica. Gravatar migró su hash de
  MD5 a SHA256 -- se usa el hash correcto y se normaliza el email
  (minúsculas, sin espacios) antes de calcularlo, porque Gravatar exige el
  valor exacto.
- **`Email → Username probable`**: la parte local del email es a menudo,
  literalmente, el username en otras plataformas. Descarta buzones
  genéricos (`info@`, `noreply@`...) para no generar ruido sin sentido.
- **`Phone → Búsqueda web`**: búsqueda inversa (dado un teléfono,
  encontrar páginas que lo mencionen), mismo patrón que
  `Domain/Person → Emails`.
- **`URL → Seguir redirecciones`**: resuelve enlaces acortados/de tracking
  hasta su destino final -- muy común encontrarlos en resultados de dorks
  o redes sociales. Con fallback a GET si el servidor no soporta HEAD.
- **`Organization → Teléfonos`**: la misma búsqueda que ya existía para
  `Domain`/`Person`, aplicada también a la empresa directamente (antes
  solo se llegaba ahí indirectamente vía `Dorks de personas y contacto`).
- **`Hash → Comprobar en Pwned Passwords`**: solo aplica a hashes SHA-1 (lo
  que usa la API). Usa el mecanismo de **k-anonimato** de HaveIBeenPwned:
  solo se envían los 5 primeros caracteres del hash, nunca el hash
  completo ni la contraseña -- la comparación final se hace en local con
  los cientos de sufijos que devuelve el servidor. Verificado explícitamente
  con test que el hash completo nunca sale de la máquina.
- **`Username → Perfil de GitLab`**: mismo patrón que GitHub, vía la API
  pública oficial. A diferencia de GitHub (que da 404 si no existe), la
  API de búsqueda de GitLab devuelve una lista vacía.

### Sobre el enriquecimiento de Person (teléfono, email, redes, empresa, ciudad)

Hasta esta ronda, `Person` solo tenía una transform (`Usernames probables`,
generación local de candidatos sin verificar). Se añaden cuatro transforms
más, todas pasivas, agrupadas por eficiencia donde una misma búsqueda ya da
varios datos útiles a la vez:

- **`Person → Emails`** y **`Person → Teléfonos`**: mismo patrón que
  `Domain → Emails`/`Domain → Teléfonos`, pero buscando el nombre de la
  persona en vez de un dominio. Como no hay un dominio conocido que filtre
  resultados, usan un regex de email/teléfono genérico (sin dominio) --
  `Person → Teléfonos` reutiliza directamente `_extract_phones()` de
  `phone_harvest_transforms.py`, ya que esa función nunca dependió de un
  dominio concreto.
- **`Person → LinkedIn y redes sociales`**: busca el nombre directamente
  (a diferencia de `Username → Otras redes`, que *adivina* un handle) y
  extrae perfiles reales de LinkedIn, X, Instagram y Facebook que aparezcan
  en los resultados de búsqueda.
- **`Person → Empresa y ciudad`**: una única búsqueda en LinkedIn que
  aprovecha dos datos distintos del mismo resultado -- la empresa se extrae
  del título (formato típico `"Nombre - Puesto - Empresa | LinkedIn"`,
  quedándose con el último segmento) y la ciudad, si aparece, del snippet
  descriptivo (heurística basada en el patrón `"Ciudad, Región, País"` que
  LinkedIn suele mostrar). La empresa se añade como nodo `Organization`
  nuevo; la ciudad, al no tener su propio tipo de entidad, se guarda como
  propiedad (`ciudad_probable`) del propio nodo `Person`.

> **Aviso de honestidad que se repite en las 4**: buscar por nombre de
> persona es inherentemente ambiguo -- un nombre común puede coincidir con
> decenas de personas sin relación entre sí. Todas marcan sus resultados
> con `confianza: baja` y dejan claro en las propiedades que hace falta
> verificar que es la persona correcta, a diferencia de transforms que
> parten de un identificador casi único (un dominio, un email).

### Sobre el puente Organization → Domain (y el resto de transforms de Organization)

Hasta esta ronda, `Organization` solo existía como *salida* de otras transforms
(WHOIS, análisis de teléfono...), nunca como entrada — un callejón sin salida
en el grafo. Se cierra con cuatro transforms:

- **`Organization → Dominio probable`**: busca el nombre de la empresa en
  DuckDuckGo y descarta automáticamente resultados de plataformas genéricas
  (LinkedIn, Wikipedia, Glassdoor...) para quedarse con candidatos que
  parecen la web propia de la empresa. Marcado con `confianza` (media/baja)
  porque es una heurística, no una fuente autoritativa — conviene verificar
  el resultado a mano antes de darlo por bueno. **Es la pieza clave**: en
  cuanto tienes el `Domain`, todo lo demás (WHOIS, MX, subdominios,
  dorking...) ya existía en el proyecto y encadena solo desde ahí. Si no
  encuentra nada, ahora explica por qué (DuckDuckGo no devolvió resultados,
  o los devolvió pero todos eran directorios genéricos) en vez de fallar
  en silencio.
- **`Organization → Dorks de personas y contacto`**: genera 5 búsquedas
  orientadas a encontrar empleados (LinkedIn), CVs, páginas de equipo y
  datos de contacto — se ejecutan con la transform `Ejecutar Dork` que ya
  existía, sin duplicar ninguna lógica.
- **`Organization → Personas vinculadas (LinkedIn)`**: a diferencia de la
  anterior (que genera un `Dork` para ejecutar aparte), esta busca
  directamente perfiles de LinkedIn y **extrae nombres reales** de personas
  del título de cada resultado (formato típico `"Nombre Apellido - Puesto -
  Empresa | LinkedIn"`), filtrando páginas de empresa/empleo por patrón de
  URL. Cierra el bucle completo que se pidió: `Organization → Person →
  Username → Otras redes` ya cubre X, Instagram, LinkedIn, Facebook,
  Pinterest, TikTok, YouTube y Telegram, encadenando con transforms que ya
  existían.
- **`Organization → Usernames probables`**: genera candidatos de handle de
  marca (normalizando sufijos legales tipo SL/Inc/LLC, y transliterando a
  ASCII) para alimentar las transforms de `Username` ya existentes.

**Dos bugs reales encontrados y arreglados** al investigar por qué a veces
no daba resultado pese a que el usuario sabía que existía un dominio:

- **Cero candidatos para nombres cortos como `"H&M"`**: el filtro de calidad
  que descartaba iniciales de menos de 3 letras (para evitar ruido tipo
  `"sl"`) podía dejar el conjunto de candidatos completamente vacío para
  marcas cortas de verdad. Se corrigió para que ese filtro nunca pueda
  vaciar el resultado entero: si tras filtrar no queda nada, se conserva
  el conjunto sin filtrar antes que no devolver nada.
- **Candidatos con tildes/eñes** (`"Telefónica España"` →
  `telefónica-españa`): ningún username real de GitHub/Reddit/redes
  sociales admite esos caracteres — un candidato así nunca podría
  encadenar con nada. Se añadió transliteración a ASCII (la misma técnica
  que ya usaba `Person → Usernames probables`), dando `telefonica-espana`.

### Sobre la verificación SMTP de buzones (Email → Verificar buzón)

Esta es una de las dos transforms marcadas como reconocimiento activo: conecta
de verdad al servidor de correo (MX) del dominio del email y usa el propio
protocolo SMTP para preguntarle si ese buzón concreto existe — sin enviar
ningún correo real (la conversación se corta justo antes del paso `DATA`,
el que transmitiría contenido).

**Límites honestos de esta técnica:**
- Proveedores grandes (Gmail, Microsoft 365...) devuelven `250 OK` para
  cualquier buzón que se les pregunte, exista o no, precisamente para
  impedir este tipo de comprobación — un resultado "existe" ahí no es fiable.
- El puerto TCP 25 está bloqueado de salida en muchísimas redes
  (residenciales, corporativas, proveedores cloud) para frenar spam. Si la
  conexión ni siquiera se establece, es casi seguro que es eso, no un fallo
  del programa — de hecho así fue durante el desarrollo: el entorno de
  pruebas bloqueaba salida SMTP.
- Lanzar muchas verificaciones seguidas contra el mismo servidor puede
  hacer que te liste como IP sospechosa.

### Sobre la auditoría de cobertura del grafo (ningún tipo sin salida)

Cada tipo de entidad que se AÑADE al proyecto debe tener, obligatoriamente,
al menos una transform que lo consuma como entrada — si no, es un nodo que
aparece en el grafo y ahí se queda, sin ningún clic derecho útil. Esto pasó
dos veces en la práctica y las dos se corrigieron:

1. **`Organization`** existía como salida de WHOIS/teléfono desde el
   principio, pero cero transforms la consumían. Se cerró con el puente
   `Organization → Dominio probable` (búsqueda web, heurística marcada con
   confianza) más generadores de dorks/usernames.
2. **`ASN`**, **`Breach`** y **`Paste`** tenían el mismo problema, detectado
   en una auditoría posterior comparando `VALID_TYPES` contra
   `TRANSFORM_REGISTRY` programáticamente. Se cerraron con transforms que
   reutilizan datos ya obtenidos siempre que fue posible (`Breach → Dominio
   de origen`, `Paste → Enlace`), sin gastar peticiones de red nuevas.
3. **`URL` era un caso más sutil**: técnicamente tenía una transform
   (`URLToDocumentMetadata`), pero solo se activa para `.pdf`/`.docx`/`.xlsx`
   — la mayoría de URLs reales del proyecto (perfiles GitHub/Reddit,
   snapshots de Wayback, resultados de dorks...) no cumplen eso y se
   quedaban sin ninguna acción. Se cerró con `URL → Dominio`, universal para
   cualquier valor, sin excepción.

Comando para repetir esta auditoría en cualquier momento:
```python
from core.entity_types import VALID_TYPES
from transforms import TRANSFORM_REGISTRY
huecos = [t for t in VALID_TYPES if not any(t in tr.input_types for tr in TRANSFORM_REGISTRY)]
print(huecos or "sin huecos")
```

### Sobre las 5 transforms pasivas más recientes

- **`IP → PTR`**: el complemento natural de `Domain → IPs`, que no tenía
  vuelta. Consulta DNS inversa pura, igual de pasiva que MX/NS.
- **`Hash → Identificar tipo`**: cálculo 100% local por prefijo/longitud.
  Importante: varios algoritmos comparten longitud exacta en hexadecimal
  (MD5, NTLM y LM hash son los tres de 32 caracteres) -- en esos casos se
  listan todos los candidatos plausibles marcados como ambiguos, en vez de
  afirmar uno con falsa certeza. Solo el contexto de dónde salió el hash
  puede desambiguarlo de verdad.
- **`IP → Shodan InternetDB`**: a diferencia del escaneo activo que se
  quitó del proyecto, esto NO toca el objetivo -- solo consulta lo que
  Shodan ya tiene indexado en su base de datos pública y gratuita
  (`internetdb.shodan.io`, sin key). Es la forma correcta de tener
  "inteligencia tipo Shodan" sin cruzar la línea hacia OSINT activo. Uso
  no comercial únicamente (condición de su servicio gratuito); la base se
  actualiza semanalmente, no es en tiempo real.
- **`IP → Geolocalización aproximada`**: vía ip-api.com. Igual que con el
  análisis de teléfonos, esto ubica la infraestructura de red (ISP/datacenter
  que anuncia ese rango), **no la posición GPS real** de nadie -- para
  VPNs/CDNs/proxies la ciudad puede no tener relación con la realidad, por
  eso se incluyen los flags de proxy/hosting que da la propia API. Nota
  técnica: su tier gratuito solo funciona por HTTP plano, no HTTPS (limitación
  de su plan gratuito) -- el dato enviado es solo la IP a consultar.
- **`Email → Clave PGP`**: nota de transparencia sobre un cambio de diseño.
  La idea original era "`Domain → Emails` vía keyserver PGP" (email
  harvesting por dominio), pero `keys.openpgp.org` no soporta esa búsqueda
  por diseño explícito de privacidad -- su documentación dice literalmente
  que solo acepta coincidencias exactas por email/fingerprint/key-id, nunca
  un listado por dominio. Se descartó esa versión antes de escribir código
  que fingiera que funcionaba. Lo que sí hace esta transform: comprobar si
  un email concreto que ya tienes en el grafo publicó su clave pública ahí
  (requiere verificación de propiedad del email por parte de su dueño, así
  que confirma que el email es real y activo).

### Bug real: cabeceras que se delataban a sí mismas como bot

Al revisar por qué las transforms basadas en DuckDuckGo (dorking, email/
teléfono harvesting, `Organization → Dominio probable`...) a veces no
devolvían nada en uso real, se encontró la causa: todas mandaban un
`User-Agent` con la firma **`"RobotEye/0.1"`** al final — literalmente lo
contrario de lo que hace falta para que un sistema anti-bot (DuckDuckGo
incluido) NO identifique la petición como automatizada. Es una cabecera
que grita "soy un scraper" en vez de camuflarse como un navegador real.

Se centralizó una cabecera de navegador real (`BROWSER_HEADERS` en
`transforms/dorking_transforms.py`: User-Agent de Chrome/Windows genuino,
`Accept`, `Accept-Language`, `Referer`) que ahora importan las 6 transforms
que hacen scraping de contenido web general (dorking, organización,
social, email/teléfono harvesting, contacto de URL, tecnologías web). Las
transforms que consultan **APIs oficiales** (GitHub, Reddit, Shodan
InternetDB, Wayback, XposedOrNot, keys.openpgp.org) mantienen su
identificador propio `"RobotEye-OSINT-Tool"`, que ahí sí es buena práctica
(esas APIs no hacen fingerprinting anti-bot como los motores de búsqueda,
y algunas incluso prefieren un User-Agent identificable).

### Sobre el email/teléfono harvesting genérico y los pivotes de Email

Cierra el resto de huecos que quedaban en la cadena
`Organization → Domain → contacto` que se pidió expresamente:

- **`Domain → Teléfonos`**: mismo patrón que `Domain → Emails`, pero para
  teléfonos. Usa `phonenumbers.PhoneNumberMatcher` (no una regex hecha a
  mano) para reconocer números válidos de múltiples regiones en texto libre.
- **`URL → Emails y teléfonos`**: a diferencia de las dos anteriores (que
  parten de un dominio y filtran por él), esta aplica a **cualquier** nodo
  URL ya existente en el grafo (un perfil de GitHub, un snapshot de
  Wayback, un resultado de un dork...) y extrae cualquier contacto visible
  en esa página concreta, sin filtrar por dominio.
- **`Email → Dominio`** y **`Email → Persona probable`**: pivotes locales
  de vuelta, sin red. El segundo intenta extraer un nombre a partir del
  patrón `nombre.apellido@` — con buzones genéricos (`info@`, `admin@`) no
  fuerza ninguna suposición sin base, simplemente no genera nada.

### Sobre el email harvesting (Domain → Emails)

Cierra un hueco que quedaba pendiente: hasta ahora podías comprobar si un
dominio tiene servidores de correo (`Domain → MX`) y verificar si un email
concreto existe (`Email → Verificar buzón`), pero no había forma de
**encontrar** direcciones de email reales asociadas a un dominio.

Funciona en dos pasos, en la misma transform: busca `"@dominio.com"` en
DuckDuckGo (los emails visibles en el propio snippet de resultados se
capturan gratis, sin petición extra), y además visita las primeras páginas
encontradas por si el email aparece en el cuerpo pero no en el fragmento
corto de búsqueda. Mismo nivel de contacto que el resto de transforms
basadas en DuckDuckGo del proyecto — no toca el dominio objetivo en ningún
momento, solo lee páginas públicas ya indexadas por un tercero.

**Límites honestos:** solo encuentra emails que ya estén publicados en
alguna página indexada — no adivina ni genera direcciones (a diferencia de
`Person → Usernames probables`, aquí todo resultado es un hallazgo real de
una página concreta). Cobertura parcial por diseño: que no aparezca nada no
significa que el dominio no tenga emails, solo que no hay ninguno publicado
en una página que DuckDuckGo haya indexado. Si una página en concreto no
responde, se descarta y se sigue con las demás sin abortar la búsqueda.

### Sobre "Ejecutar todas" (inspirado en Maltego)

Se documentó primero cómo funciona exactamente esto en Maltego (artículo
oficial *The Run Transforms Menu*) para no replicar algo a medias por
intuición: en Maltego, **"All Transforms"** no ejecuta nada de golpe — es
un atajo que se salta el nivel de categorías ("Sets") y va directo a la
lista plana de transforms, donde sigues eligiendo una por una. Lo que
**sí** ejecuta varias a la vez es el icono `>>` ("Run all in this Set"),
que lanza todas las transforms de un grupo de una tacada, con una barra de
progreso conjunta.

RobotEye no tiene el concepto de "Sets" (agrupación en categorías), así
que se replicó el espíritu del `>>`: el botón **`▶▶ Ejecutar todas (N)`**
lanza de golpe todas las transforms **pasivas** aplicables a un nodo.
Cada una crea su propio `TransformWorker` (QThread), así que corren en
paralelo de verdad — probado con DNS real sobre `example.com`: 12
transforms concurrentes, resultados y errores de red individuales
llegando de forma intercalada según cada una termina, sin que un fallo
puntual de una interfiera con las demás.

**Las transforms de reconocimiento activo nunca se incluyen** en "Ejecutar
todas" — bajo ningún concepto, ni con confirmación agrupada. Cada una
sigue exigiendo su propio diálogo de consentimiento individual, tal y como
se diseñó. Si hay alguna aplicable al nodo, el log lo indica explícitamente
tras la ejecución masiva, para que sepas que existen y las lances a mano
si te interesan.

### Sobre el Google Dorking

Está dividido en dos pasos a propósito:

1. **`Domain → Google Dorks (sugeridos)`** genera 12 queries típicas de dorking
   (`site:dominio filetype:pdf`, `inurl:admin`, `intitle:"index of"`, ficheros
## Añadir una transform nueva

1. Crea una clase en `transforms/tu_modulo.py` que herede de `Transform`
   (`core/transform_base.py`), define `name`, `input_types` y el método `run()`.
2. Decórala con `@register`.
3. Impórtala en `transforms/__init__.py`.

Aparecerá automáticamente en el menú contextual de los nodos cuyo tipo
coincida con `input_types`, sin tocar nada más del core ni de la UI.

## Empaquetar como ejecutable (.exe / binario Linux)

### Opción A: automático con GitHub Actions (recomendado)

El repo incluye `.github/workflows/build.yml`, que compila en runners nativos
de Windows y Linux en paralelo (nada de cross-compiling ni Wine — se probó
la vía Wine para poder generar el `.exe` sin salir de un entorno Linux, y
se descartó a propósito: aunque la compilación "termine", no hay forma de
verificar desde Linux que el binario resultante arranque de verdad en
Windows real, porque la emulación de Win32 de Wine tiene lagunas conocidas
justo en las áreas que más usa Qt/PySide6. Mejor un runner Windows real):

1. Sube el proyecto a un repo de GitHub.
2. Para compilar sin publicar nada (solo probar): pestaña **Actions** →
   *Build RobotEye* → **Run workflow** (botón manual). Al terminar, los dos
   binarios quedan descargables como *artifacts* de esa ejecución.
3. Para sacar una release de verdad: crea y sube un tag con versión semántica:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Esto dispara el build en ambos SO y, al terminar, crea automáticamente un
   **Release** en GitHub con `RobotEye-windows.exe` y `RobotEye-linux`
   adjuntos, listos para descargar.

El workflow instala las librerías de sistema que PySide6 necesita en el
runner de Linux (`libxcb-cursor0` y compañía — sin ellas el binario compila
pero no arranca), así que no hace falta tocar nada más.

### Opción B: manual, compilar en tu propia máquina

Hay que compilar en cada sistema operativo objetivo (PyInstaller no cruza SO):

```bash
# En Windows, con el venv activado:
pyinstaller --name RobotEye --windowed --onefile main.py
# → dist/RobotEye.exe

# En Linux, con el venv activado:
pyinstaller --name RobotEye --windowed --onefile main.py
# → dist/RobotEye
```

Notas:
- `--onefile` es más cómodo de distribuir pero arranca algo más lento
  (descomprime en un directorio temporal). Si prefieres arranque rápido,
  usa `--onedir` en su lugar.
- Algunos antivirus de Windows dan falso positivo con binarios PyInstaller
  `--onefile` sin firmar; es un problema conocido del propio PyInstaller.

## Tests

Toda la rigurosidad de pruebas aplicada durante el desarrollo (baterías de
casos límite reales, regresiones de bugs históricos, mocks fieles a
esquemas de API documentados) vive ahora en `tests/`, no solo en el
historial de la conversación que la produjo. **190 tests**, organizados
en 13 módulos:

```
tests/
├── conftest.py                    # QApplication de sesión + fixtures compartidas
├── test_core_model.py             # GraphModel, dedup, persistencia JSON/SQLite
├── test_entity_coverage.py        # auditoría automática: ningún tipo es callejón sin salida
├── test_transforms_local.py       # transforms 100% locales (deben funcionar siempre)
├── test_transforms_network.py     # transforms de red, mocks fieles a esquemas reales
├── test_ui_regressions.py         # bugs históricos de UI + flujo de consentimiento
├── test_bulk_import.py            # autodetección de tipo + importación masiva
├── test_report_generator.py       # informes HTML/PDF, incluido escapado de HTML peligroso
├── test_email_analyzer.py         # análisis de .eml, incluidos los 2 falsos positivos corregidos
├── test_public_content.py         # búsqueda automática de documentos y publicaciones públicas
├── test_canvas_search.py          # búsqueda en el lienzo + resaltado temporal de nodo
├── test_delete_confirmation.py    # confirmación antes de borrar + conteo de conexiones
├── test_user_notes.py             # notas manuales del usuario, persistencia e informes
└── test_activity_log.py           # registro de actividad estructurado y su exportación
```

```bash
pip install -r requirements-dev.txt   # añade pytest y pytest-qt sobre requirements.txt
pytest                                 # corre toda la suite (config en pytest.ini)
```

`test_entity_coverage.py` merece mención aparte: convierte en test
permanente la auditoría manual (basada en AST) que se repitió muchas veces
durante el desarrollo para detectar tipos de entidad "callejón sin salida"
-- si alguien añade una transform nueva que genera un tipo de entidad sin
que ninguna otra lo consuma, este test falla solo, sin depender de que
alguien se acuerde de volver a auditar a mano.

`requirements-dev.txt` es aparte de `requirements.txt` a propósito:
`pytest`/`pytest-qt` no deben acabar empaquetados dentro del `.exe` final,
solo hacen falta en desarrollo/CI.

El workflow de GitHub Actions (`.github/workflows/build.yml`) ejecuta la
suite completa en Linux y Windows **antes** de compilar -- si un test
falla, ni siquiera se intenta generar el binario (`build` depende de
`test` vía `needs:`).

## Estructura

```
roboteye/
├── main.py
├── .github/workflows/build.yml  # CI: compila .exe (Windows) + binario (Linux)
├── core/
│   ├── graph_model.py       # nodos, aristas, persistencia JSON/SQLite (networkx)
│   ├── entity_types.py      # Entity + tipos válidos + guess_entity_type() (import masivo)
│   ├── transform_base.py    # clase abstracta Transform + registro
│   ├── transform_runner.py  # ejecución en QThread
│   ├── report_generator.py  # informes HTML/PDF (Exportar informe)
│   └── email_analyzer.py    # analizador de .eml (Analizar email sospechoso)
├── transforms/
│   ├── dns_transforms.py
│   ├── whois_transforms.py
│   ├── crtsh_transforms.py
│   ├── dorking_transforms.py
│   ├── xposedornot_transforms.py
│   ├── phone_transforms.py
│   ├── social_transforms.py
│   ├── wayback_transforms.py
│   ├── metadata_transforms.py
│   ├── asn_transforms.py
│   ├── emailsec_transforms.py
│   ├── username_gen_transforms.py
│   ├── ptr_transforms.py
│   ├── hash_transforms.py
│   ├── shodan_internetdb_transforms.py
│   ├── geolocation_transforms.py
│   ├── pgp_transforms.py
│   ├── webtech_transforms.py  # reconocimiento activo, requires_consent=True
│   ├── organization_transforms.py
│   ├── smtp_verify_transforms.py  # reconocimiento activo, requires_consent=True
│   ├── breach_paste_transforms.py
│   ├── url_transforms.py
│   ├── email_harvest_transforms.py
│   ├── email_pivot_transforms.py
│   ├── phone_harvest_transforms.py
│   ├── url_contact_transforms.py
│   ├── person_enrichment_transforms.py
│   ├── ip_enrichment_transforms.py
│   ├── email_enrichment_transforms.py
│   ├── url_redirect_transforms.py
│   ├── hash_pwned_transforms.py
│   ├── darkweb_transforms.py
│   ├── image_metadata_transforms.py
│   ├── ssl_cert_transforms.py
│   ├── cve_transforms.py
│   ├── mac_vendor_transforms.py
│   └── public_content_transforms.py
├── ui/
│   ├── theme.py              # paleta cyberpunk + fuentes, punto único de verdad
│   ├── main_window.py       # QMainWindow, menús, panel lateral
│   ├── graph_view.py        # QGraphicsView (zoom/pan, fondo tipo Tron)
│   ├── graph_scene.py       # QGraphicsScene, sincroniza con GraphModel
│   ├── node_item.py         # nodo arrastrable (glow neón + color por tipo)
│   └── edge_item.py         # arista entre nodos, se actualiza al mover
├── tests/                   # 103 tests (ver sección "Tests" más arriba)
├── pytest.ini
├── requirements.txt
└── requirements-dev.txt     # requirements.txt + pytest/pytest-qt (no se empaqueta en el .exe)
```

## Estética visual (hacker / cyberpunk)

Toda la paleta de colores y fuentes vive en un único fichero,
`ui/theme.py`, para no tener valores hex sueltos repartidos por el código:

- **Fondo**: negro-azulado (`#05070d`/`#0a0e17`), con un fondo de canvas
  tipo Tron: rejilla tenue + halo radial cian muy sutil, en vez del blanco
  por defecto de Qt (`ui/graph_view.py`, `GraphView.drawBackground`).
- **Nodos**: relleno "cristal neón" (el color del tipo a baja opacidad) con
  borde neón sólido y un glow (`QGraphicsDropShadowEffect`) del mismo color
  alrededor — cada tipo de entidad tiene su propio color de acento
  (Domain=cian, IP=verde, Breach=carmesí, Person=magenta...).
- **Tipografía**: monoespaciada estilo terminal en toda la app (JetBrains
  Mono / Cascadia Code / Consolas / Fira Code, con fallback a `monospace`
  si ninguna está instalada — `QFont.setFamilies`, prueba cada una en orden).
- **Paneles**: cabeceras tipo consola (`[ DETALLES ]`, `[ LOG ]`...) con su
  propio color de acento; el log usa verde tipo terminal con prompt `>` y
  resalta errores en rojo automáticamente.
- **Menús**: fondo oscuro con borde cian, hover en magenta — incluida la
  separación visual de la sección de reconocimiento activo con su aviso.

## Próximos pasos sugeridos

- Firmar el .exe si el falso positivo de antivirus resulta molesto en distribución.
- Ampliar `Domain → Emails` a más de un motor de búsqueda (ahora mismo solo
  usa DuckDuckGo) para mejorar cobertura.
