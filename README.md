# 🚗 ITV Argentona Scraper

Scraper automatizado para buscar citas disponibles en la ITV de Argentona (Applus+).

## 📋 Descripción

Este proyecto es un web scraper que automatiza la búsqueda de citas disponibles en la estación de ITV de Argentona, gestionada por Applus+. El scraper accede al portal de citas online, ingresa la matrícula del vehículo y busca las fechas disponibles.

## 🌐 Portal de Citas

- **URL**: https://aibs.appluscorp.com/?MenuActivo=mrNuevaReserva
- **Gestión de reservas**: https://aibs.appluscorp.com/?MenuActivo=mrGestionReserva
- **Estación**: ITV Argentona (Barcelona, Catalunya)

## 🚀 Instalación

### Requisitos Previos

- Python 3.8 o superior
- Google Chrome instalado
- pip (gestor de paquetes de Python)

### Pasos de Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/hmgsystray/Itv-scrapper.git
cd Itv-scrapper
```

2. Crear un entorno virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # En Linux/Mac
# o
venv\Scripts\activate  # En Windows
```

3. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar las variables de entorno:
```bash
cp config.example.env .env
```

5. Editar el archivo `.env` con tus datos:
```env
LICENSE_PLATE=1234ABC
HEADLESS=true
SCREENSHOT=true
```

## 📖 Uso

### Uso Básico

Ejecutar el scraper con tu matrícula configurada en `.env`:

```bash
python itv_scraper.py
```

### Uso Programático

También puedes usar el scraper en tus propios scripts de Python:

```python
from itv_scraper import ITVArgentona

# Crear instancia del scraper
scraper = ITVArgentona(
    license_plate="1234ABC",
    headless=False,  # Ver el navegador
    take_screenshots=True
)

# Buscar citas
appointments = scraper.search_appointments()

# Procesar resultados
for apt in appointments:
    print(f"Cita disponible: {apt}")
```

## ⚙️ Configuración

### Variables de Entorno

| Variable | Descripción | Valores | Por Defecto |
|----------|-------------|---------|-------------|
| `LICENSE_PLATE` | Matrícula del vehículo (sin espacios) | Ej: `1234ABC` | Requerido |
| `HEADLESS` | Ejecutar navegador sin interfaz gráfica | `true`/`false` | `true` |
| `SCREENSHOT` | Tomar capturas de pantalla | `true`/`false` | `true` |

## 📂 Estructura del Proyecto

```
Itv-scrapper/
├── itv_scraper.py          # Scraper principal
├── requirements.txt        # Dependencias de Python
├── config.example.env      # Ejemplo de configuración
├── .env                    # Configuración personal (no incluir en git)
├── .gitignore             # Archivos a ignorar por git
├── README.md              # Esta documentación
├── screenshots/           # Capturas de pantalla (generadas automáticamente)
└── output/               # Archivos de salida HTML (generados automáticamente)
```

## 🛠️ Funcionalidades

- ✅ Acceso automatizado al portal de Applus+
- ✅ Búsqueda de citas por matrícula
- ✅ Capturas de pantalla del proceso
- ✅ Modo headless para ejecución en servidores
- ✅ Manejo de errores y logging detallado
- ✅ Guardado de HTML para análisis manual
- ✅ Anti-detección básica (user-agent, webdriver properties)

## 📸 Capturas de Pantalla

El scraper toma automáticamente capturas de pantalla durante el proceso:

1. `01_pagina_inicial.png` - Página inicial del portal
2. `02_matricula_ingresada.png` - Después de ingresar la matrícula
3. `03_despues_de_buscar.png` - Resultados de la búsqueda
4. `error_*.png` - Capturas en caso de error

Las capturas se guardan en la carpeta `screenshots/` con timestamp.

## 🔧 Solución de Problemas

### Error: No se encuentra el campo de matrícula

El portal puede haber cambiado su estructura. Verifica:
1. Las capturas en `screenshots/`
2. El archivo HTML en `output/page_content.html`
3. Actualiza los selectores CSS en el código si es necesario

### Error: Chrome driver no compatible

```bash
pip install --upgrade webdriver-manager
```

### El navegador se cierra muy rápido

Cambia `HEADLESS=false` en `.env` para ver qué ocurre.

## 📝 Notas Importantes

- **Uso Responsable**: Este scraper es para uso personal. No hagas peticiones excesivas que puedan sobrecargar el servidor.
- **Cambios en el Portal**: Si Applus+ cambia su portal, el scraper puede dejar de funcionar y requerir actualizaciones.
- **Privacidad**: No compartas tu archivo `.env` ya que contiene tu matrícula.

## 🗓️ Información de la ITV Argentona

- **Dirección**: Polígon Industrial El Cros, 08310 Argentona, Barcelona
- **Teléfono**: 93 799 42 11 / 902 93 02 00
- **Horario**:
  - Lunes a Viernes: 6:30 - 21:00
  - Sábados: 8:00 - 14:00

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## ⚠️ Disclaimer

Este proyecto no está afiliado, asociado, autorizado ni respaldado por Applus+ ni por ninguna de sus filiales. Es un proyecto independiente creado con fines educativos y de automatización personal.

El uso de este scraper es bajo tu propia responsabilidad. Asegúrate de cumplir con los términos de servicio del portal de Applus+.

## 🔗 Enlaces Útiles

- [Portal Oficial Applus+ ITV](https://www.applusiteuve.com/)
- [ITV Argentona](https://www.applusiteuve.com/en/estaciones-itv/itv-catalunya/itv-barcelona/itv-argentona/)
- [Sistema de Reservas](https://aibs.appluscorp.com/)

---

Desarrollado con ❤️ para facilitar la reserva de citas en la ITV
