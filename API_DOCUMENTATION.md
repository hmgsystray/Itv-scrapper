# API Documentation - ITV Argentona

## Endpoint descubierto mediante interceptación HTTP

Este documento describe el endpoint de API REST que devuelve las fechas y horas disponibles para reservas en ITV Argentona.

---

## Flujo completo de autenticación y acceso

### PASO 1: Obtener guidSesion

**Endpoint:**
```
GET /Reserva/ReservarMatricula
```

**URL completa:**
```
https://aibs.appluscorp.com/Reserva/ReservarMatricula?language=es&AppCentro=B08&Matricula={PLATE}
```

**Parámetros:**
- `language`: `es` (español), `ca` (catalán), `eu` (euskera), `en` (inglés)
- `AppCentro`: `B08` (código de ITV Argentona)
- `Matricula`: Matrícula del vehículo sin espacios (ej: `3332FSS`)

**Respuesta:**
- Formato: HTML
- Contiene JavaScript con la variable `guidSesion`
- Extraer con regex: `guidSesion["\s=:]+([a-f0-9\-]{36})`

**Ejemplo de extracción:**
```javascript
var guidSesion = "ce597c77-b5ec-483a-aa70-47e76a0e583a";
```

---

### PASO 2: Navegar a Eleccion_Estacion

**Endpoint:**
```
GET /Reserva/NavegarAVistaSiguiente
```

**URL completa:**
```
https://aibs.appluscorp.com/Reserva/NavegarAVistaSiguiente?guidSesion={GUID}&actualViewName=Datos_Contacto
```

**Parámetros:**
- `guidSesion`: GUID obtenido en el paso 1
- `actualViewName`: `Datos_Contacto`

**Respuesta:**
- Formato: HTML
- Página de confirmación del centro ITV

---

### PASO 3: Navegar a página de fechas

**Endpoint:**
```
GET /Reserva/NavegarAVistaSiguiente
```

**URL completa:**
```
https://aibs.appluscorp.com/Reserva/NavegarAVistaSiguiente?guidSesion={GUID}&actualViewName=Eleccion_Estacion
```

**Parámetros:**
- `guidSesion`: GUID obtenido en el paso 1
- `actualViewName`: `Eleccion_Estacion`

**Respuesta:**
- Formato: HTML
- Página "Elige fecha" con calendario
- Contiene JavaScript que llama al endpoint de API

---

### PASO 4: Obtener fechas disponibles (API PRINCIPAL)

**Endpoint:**
```
GET /Reserva/GetFechasHorasDisponibles
```

**URL completa:**
```
https://aibs.appluscorp.com/Reserva/GetFechasHorasDisponibles?guidSesion={GUID}&mes={MM}&anyo={YYYY}
```

**Parámetros:**
- `guidSesion`: GUID obtenido en el paso 1
- `mes`: Mes en formato `MM` (ej: `01`, `11`)
- `anyo`: Año en formato `YYYY` (ej: `2025`)

**Headers requeridos:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: es-ES,es;q=0.9
Referer: https://www.applusiteuve.com/
```

**Respuesta:**
- Formato: **JSON**
- Content-Type: `application/json; charset=utf-8`
- Tamaño típico: ~400 KB

---

## Estructura de la respuesta JSON

### Nivel superior

```json
{
  "calendarioSePuedeIrAtras": false,
  "calendarioSePuedeIrAdelante": true,
  "dias": [ ... ]
}
```

**Campos:**
- `calendarioSePuedeIrAtras`: (bool) Si se puede navegar al mes anterior
- `calendarioSePuedeIrAdelante`: (bool) Si se puede navegar al mes siguiente
- `dias`: (array) Lista de todos los días del mes

---

### Estructura de cada día

```json
{
  "FechaString": "2025-11-07",
  "FechaStringFormat": "07 nov. 2025",
  "Seleccionable": false,
  "PrecioDesde": null,
  "PrimeraHoraDisponible": null,
  "horas": [ ... ],
  "TipoDia": "vacio",
  "NumTarifaCSSMaxima": 0,
  "TieneDescuentos1": false,
  "TieneDescuentos2": false,
  "TieneDescuentos3": false,
  "TieneDescuentos4": false,
  "TieneDescuentos5": false,
  "TieneDescuentos6": false,
  "DescripcionDescuentoHorarioTarifa1": "",
  "DescripcionDescuentoHorarioTarifa2": "",
  "DescripcionDescuentoHorarioTarifa3": "",
  "DescripcionDescuentoHorarioTarifa4": "",
  "DescripcionDescuentoHorarioTarifa5": "",
  "DescripcionDescuentoHorarioTarifa6": ""
}
```

**Campos importantes:**
- `FechaString`: Fecha en formato ISO (YYYY-MM-DD)
- `FechaStringFormat`: Fecha formateada para mostrar
- `Seleccionable`: Si el día tiene citas disponibles
- `PrecioDesde`: Precio mínimo del día (null si no hay disponibilidad)
- `PrimeraHoraDisponible`: Primera hora disponible del día (null si no hay)
- `horas`: Array de slots horarios cada 15 minutos
- `TipoDia`: Tipo de día (`"vacio"`, `"disponible"`, etc.)

---

### Estructura de cada hora

```json
{
  "TipoHora": "no_disponible",
  "Hora": "06:00",
  "Disponible": false,
  "PrecioAnterior": 40.6,
  "Precio": 40.6,
  "IdDescuentoHorario": null,
  "NumTarifaCSS": 0,
  "DescripcionDescuentoHorarioTarifa": null
}
```

**Campos importantes:**
- `TipoHora`: Tipo de slot (`"no_disponible"`, `"disponible"`, etc.)
- `Hora`: Hora en formato HH:MM (slots cada 15 minutos)
- `Disponible`: **CAMPO CLAVE** - `true` si está disponible, `false` si no
- `Precio`: Precio de la cita (ej: 40.6 EUR)
- `PrecioAnterior`: Precio anterior (para mostrar descuentos)

---

## Algoritmo para extraer citas disponibles

```python
def extraer_citas_disponibles(json_response):
    citas = []

    for dia in json_response['dias']:
        if not dia['Seleccionable']:
            continue  # Saltar días sin disponibilidad

        fecha = dia['FechaString']  # "2025-11-07"

        for hora in dia['horas']:
            if hora['Disponible']:  # Solo slots disponibles
                citas.append({
                    'fecha': fecha,
                    'hora': hora['Hora'],
                    'precio': hora['Precio'],
                    'fecha_hora': f"{fecha} {hora['Hora']}"
                })

    return citas
```

---

## Ejemplo de cURL

```bash
# Paso 1: Obtener guidSesion
curl 'https://aibs.appluscorp.com/Reserva/ReservarMatricula?language=es&AppCentro=B08&Matricula=3332FSS' \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'Accept: text/html' \
  | grep -oP 'guidSesion["\s=:]+\K[a-f0-9\-]{36}'

# Paso 2: Navegar (usar el GUID del paso anterior)
GUID="ce597c77-b5ec-483a-aa70-47e76a0e583a"

curl "https://aibs.appluscorp.com/Reserva/NavegarAVistaSiguiente?guidSesion=$GUID&actualViewName=Datos_Contacto" \
  -H 'User-Agent: Mozilla/5.0'

# Paso 3: Navegar a página de fechas
curl "https://aibs.appluscorp.com/Reserva/NavegarAVistaSiguiente?guidSesion=$GUID&actualViewName=Eleccion_Estacion" \
  -H 'User-Agent: Mozilla/5.0'

# Paso 4: Obtener fechas disponibles (API)
curl "https://aibs.appluscorp.com/Reserva/GetFechasHorasDisponibles?guidSesion=$GUID&mes=11&anyo=2025" \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'Accept: application/json'
```

---

## Ejemplo de código Python completo

```python
import requests
import re
from datetime import datetime

# Configuración
BASE_URL = "https://aibs.appluscorp.com"
LICENSE_PLATE = "3332FSS"

# Crear sesión
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'es-ES,es;q=0.9'
})

# PASO 1: Obtener guidSesion
r1 = session.get(f"{BASE_URL}/Reserva/ReservarMatricula", params={
    'language': 'es',
    'AppCentro': 'B08',
    'Matricula': LICENSE_PLATE
})

guid = re.search(r'guidSesion["\s=:]+([a-f0-9\-]{36})', r1.text).group(1)
print(f"guidSesion: {guid}")

# PASO 2: Navegar a Eleccion_Estacion
session.get(f"{BASE_URL}/Reserva/NavegarAVistaSiguiente", params={
    'guidSesion': guid,
    'actualViewName': 'Datos_Contacto'
})

# PASO 3: Navegar a página de fechas
session.get(f"{BASE_URL}/Reserva/NavegarAVistaSiguiente", params={
    'guidSesion': guid,
    'actualViewName': 'Eleccion_Estacion'
})

# PASO 4: Obtener fechas disponibles
now = datetime.now()
response = session.get(f"{BASE_URL}/Reserva/GetFechasHorasDisponibles", params={
    'guidSesion': guid,
    'mes': f"{now.month:02d}",
    'anyo': str(now.year)
})

data = response.json()

# Extraer citas disponibles
citas = []
for dia in data['dias']:
    if not dia['Seleccionable']:
        continue

    for hora in dia['horas']:
        if hora['Disponible']:
            citas.append({
                'fecha': dia['FechaString'],
                'hora': hora['Hora'],
                'precio': hora['Precio']
            })

print(f"\nCitas disponibles encontradas: {len(citas)}")
for cita in citas[:10]:  # Mostrar las primeras 10
    print(f"  {cita['fecha']} {cita['hora']} - {cita['precio']}€")
```

---

## Notas importantes

### Sesión y cookies
- La sesión se mantiene mediante el `guidSesion` en la URL
- Las cookies HTTP estándar se gestionan automáticamente con `requests.Session()`
- No requiere autenticación de usuario

### Lifetime del guidSesion
- Desconocido, probablemente 15-30 minutos
- Si expira, se debe reiniciar el flujo desde el paso 1
- No hay mecanismo de refresh token

### Rate limiting
- No se detectaron límites estrictos
- Recomendación: No hacer peticiones más frecuentes de 1 petición/minuto
- Para monitoreo continuo: usar intervalos de 5 minutos

### Manejo de errores
- Error 500: Suele indicar que falta algún parámetro o el flujo no se siguió correctamente
- Sesión expirada: El HTML devuelve mensaje "Upps... Parece que ha perdido los datos de sesión"
- En caso de error: reiniciar desde el paso 1

---

## Ventajas de usar el endpoint de API

✅ **Respuesta en JSON**: Fácil de parsear, no necesita BeautifulSoup
✅ **Datos estructurados**: Información completa de disponibilidad
✅ **Rápido**: Solo 4 peticiones HTTP para obtener todas las fechas
✅ **Confiable**: No depende de la estructura HTML del frontend
✅ **Completo**: Incluye precios, descuentos, y todos los slots horarios

---

## Changelog

- **2025-11-07**: Documentación inicial basada en interceptación HTTP real

