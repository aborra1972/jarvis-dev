# Comandos de Voz — Referencia Rápida

## Cómo usar

1. Decí la palabra de activación configurada
2. Decí tu comando
3. Escuchá la respuesta

---

## Comandos

### Sistema
- "abrí la terminal"
- "abri el explorador de archivos"
- "abrí firefox" / "abri el navegador"
- "cerrá firefox" / "cierra el navegador"

### Archivos
- "creá una carpeta llamada [nombre]"
- "creá un archivo [nombre]"
- "borrá el archivo [nombre]"

### Web
- "buscá [término] en internet"
- "abri [sitio web]"
- "abri google"

### Desarrollo
- "mostrá el estado del proyecto"
- "creá un commit con mensaje [texto]"
- "mostrá los últimos commits"

### Spotify local (Stage 1)
- "reproducir spotify" / "reproducí spotify"
- "pausar spotify" / "pausá spotify"

El control local usa únicamente el reproductor MPRIS de Spotify Desktop ya abierto,
no requiere OAuth, credenciales ni red, y falla cerrado si `playerctl` falta,
Spotify no aparece o hay más de un reproductor coincidente. Abrir Spotify sigue
usando el comando existente `open_app`.

Para revisar la capacidad local sin exponer salida del proceso, ejecutá el
diagnóstico con sondeo de host explícito desde el checkout:

```bash
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev
SPOTIFY_LOCAL_ENABLED=true jarvis/.venv/bin/python -c \
  'from jarvis.diagnose import check_spotify_local; print(check_spotify_local(probe=True))'
```

El diagnóstico solo informa estados normalizados: `disabled`, `missing`,
`ambiguous` o `available`. El sondeo no se ejecuta por defecto; no muestra
stdout/stderr, argumentos, rutas configuradas ni secretos. Un estado `missing`
o `ambiguous` bloquea cualquier control y no selecciona otro reproductor.
Stage 2 (búsqueda, reproducción por API y OAuth) permanece fuera de este
límite y requiere autorización explícita posterior.

### Spotify por API (Stage 2, opt-in explícito)

Stage 2 está deshabilitado por defecto. Solo se habilita con una configuración
local explícita y después de autorizar la integración de Spotify; no alcanza la
confirmación de una acción destructiva. La autorización usa OAuth Authorization
Code con PKCE y solicita exactamente estos permisos mínimos:
`user-read-playback-state` y `user-modify-playback-state`. La cuenta debe ser
Spotify Premium.

Stage 1 es local y offline: controla el Spotify Desktop local mediante MPRIS.
Stage 2 es la frontera de red: búsqueda de álbumes/artistas y reproducción por
la API oficial pueden enviar la consulta a Spotify, únicamente con Stage 2
habilitado y autorizado. Si Stage 2 está apagado, no hay credenciales, el
keyring no está disponible, la autorización venció o fue revocada, o falla la
red, la operación falla cerrada y Stage 1 sigue siendo utilizable.

La búsqueda no reproduce automáticamente. Si devuelve varios álbumes o artistas,
Jarvis debe mostrar una lista numerada acotada y pedir aclaración obligatoria;
solo acepta el número o la referencia pendiente exacta. No elige automáticamente
ni interpreta texto libre como selección.

La reproducción API apunta únicamente a **Spotify Desktop en esta PC**: exige
una única coincidencia del destino configurado y su verificación local. No cambia
de dispositivo ni usa Spotify Connect, otro reproductor, navegador, automatización
del navegador o fallback MPRIS; ante un destino ausente, ambiguo o no reproducible
no reproduce ni afirma éxito.

Para deshabilitar Stage 2, apagá la integración y eliminá sus credenciales del
keyring. Para revocar, ejecutá el flujo de revocación y eliminá también el estado
local; luego autorizá de nuevo solo si querés reactivarlo. El rollback de Stage 2
no modifica Stage 1: conserva `open_app spotify` y el control local independiente.

Nunca guardes tokens, refresh tokens, códigos OAuth, verifiers, estados, secretos,
URLs de callback ni respuestas crudas del catálogo en el repositorio, historial,
logs, prompts, TTS o diagnósticos. Usá únicamente el keyring del sistema; si no
está disponible, no se crea un archivo alternativo ni se continúa con la API.

### Asistente
- "¿Qué podés hacer?"
- "¿Cuál es tu nombre?"
- "apagá" / "power off"

### Recordatorios
- "recordame sacar la ropa en 10 minutos"
- "recordame revisar el horno en media hora"
- "recordame llamar a mamá a las 3 pm"
- "recordame tomar el remedio a las 21:30"

---

## Solución rápida

| Problema | Solución |
|----------|----------|
| No detecta | Bajá el umbral (slider a 0.3) |
| Se activa solo | Subí el umbral (slider a 0.7) |
| No hay audio | Verificá `arecord -l` |
| No ejecuta | Verificá proyecto activo |
