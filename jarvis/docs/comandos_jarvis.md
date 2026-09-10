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
