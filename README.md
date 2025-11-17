# ITV Scraper & Monitor

Monitor automatizado para buscar citas disponibles en estaciones ITV de Applus+ con notificaciones a Discord.

## Descripción

Sistema de monitoreo continuo que:
- Busca automáticamente citas disponibles en estaciones ITV
- Detecta nuevas citas comparando con búsquedas anteriores
- Envía notificaciones a Discord cuando aparecen nuevas citas
- Soporta múltiples estaciones y matrículas simultáneamente
- Usa API REST directa (rápido y eficiente)

## Instalación

### Requisitos

- Python 3.8 o superior
- pip

### Pasos

1. Clonar el repositorio:
```bash
git clone https://github.com/hmgsystray/Itv-scrapper.git
cd Itv-scrapper
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar el archivo `.env`:
```bash
cp .env.example .env
```

4. Editar `.env` con tu configuración (ver sección Configuración)

## Configuración

Edita el archivo `.env`:

```bash
# Estaciones a monitorizar (formato: CODIGO:MATRICULA:NOMBRE)
STATIONS=B08:6784BDR:ITV Argentona

# Discord webhook (opcional, si no se configura solo muestra en terminal)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/TU_WEBHOOK

# Intervalo de revisión en minutos (default: 5)
MONITOR_INTERVAL_MINUTES=5

# Días límite para notificar (default: 45)
DAYS_LIMIT=45
```

### Formato de STATIONS

**Formato:** `CODIGO:MATRICULA:NOMBRE`

**Ejemplos:**
```bash
# Una estación
STATIONS=B08:6784BDR:ITV Argentona

# Múltiples estaciones
STATIONS=B08:6784BDR:ITV Argentona,B07:6146CXR:ITV Mollet,B01:1234ABC:ITV Barcelona

# Con matrícula aleatoria (dejar campo vacío)
STATIONS=B08::ITV Argentona

# Sin nombre personalizado (usará "ITV B08")
STATIONS=B08:6784BDR
```

### Códigos de estaciones comunes

- **B08**: ITV Argentona
- **B07**: ITV Mollet del Vallès
- **B01**: ITV Barcelona

### Configurar Discord Webhook

1. Abre Discord y ve al canal donde quieres recibir notificaciones
2. Click en ⚙️ Ajustes del canal → Integraciones → Webhooks
3. Click en Nuevo Webhook
4. Copia la URL del webhook
5. Pégala en `.env` en `DISCORD_WEBHOOK_URL`

Probar webhook:
```bash
python discord_notifier.py
```

## Uso

### Monitor Continuo (Recomendado)

Inicia el monitor que revisará automáticamente y enviará notificaciones:

```bash
python itv_monitor.py
```

El monitor:
- Revisa cada X minutos (configurado en `MONITOR_INTERVAL_MINUTES`)
- Detecta solo citas nuevas (no envía duplicados)
- Notifica instantáneamente en Discord
- Se puede dejar corriendo 24/7

**Presiona `Ctrl+C` para detener**

### Búsqueda Única

Para hacer solo una búsqueda sin monitoreo:

```bash
python itv_scraper.py
```

## Estructura del Proyecto

```
Itv-scrapper/
├── itv_scraper.py          # Scraper principal
├── itv_monitor.py          # Monitor continuo
├── discord_notifier.py     # Notificaciones Discord
├── requirements.txt        # Dependencias
├── .env.example           # Ejemplo de configuración
├── .env                   # Tu configuración (no incluir en git)
├── README.md              # Esta documentación
├── CLAUDE.md              # Guía para Claude Code
├── API_DOCUMENTATION.md   # Documentación de la API
└── monitor_state.json     # Estado del monitor (generado automáticamente)
```

## Características Técnicas

- **API REST**: Usa endpoint `/Reserva/GetFechasHorasDisponibles` directamente
- **JSON**: Procesa respuestas JSON (no parsing HTML)
- **Multi-estación**: Monitoriza múltiples estaciones simultáneamente
- **Multi-matrícula**: Cada estación puede tener su propia matrícula
- **Deduplicación**: Sistema hash para evitar notificaciones duplicadas
- **Estado persistente**: Guarda estado entre reinicios

## Solución de Problemas

### Error: No se pudo obtener guidSesion

- Verifica que la matrícula sea válida
- El portal puede estar temporalmente caído
- Intenta de nuevo en unos minutos

### Error: HTTP 500

- La matrícula puede tener una reserva activa
- Intenta con otra matrícula
- El servidor puede estar sobrecargado

### No recibo notificaciones en Discord

- Verifica que `DISCORD_WEBHOOK_URL` sea correcta
- Prueba con: `python discord_notifier.py`
- Si el webhook no funciona, las notificaciones se muestran en terminal

## Notas Importantes

- **Uso responsable**: No usar intervalos menores a 1 minuto
- **Privacidad**: No compartir el archivo `.env` (contiene tu matrícula)
- **Cambios en API**: Si Applus+ cambia su API, el scraper puede necesitar actualizaciones

## Enlaces Útiles

- [Portal Applus+ ITV](https://www.applusiteuve.com/)
- [Sistema de Reservas](https://aibs.appluscorp.com/)

## Disclaimer

Este proyecto no está afiliado con Applus+. Es un proyecto independiente para automatización personal. Uso bajo tu propia responsabilidad.

---

Desarrollado para facilitar la reserva de citas en la ITV
