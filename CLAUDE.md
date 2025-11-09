# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ITV Argentona Scraper & Monitor - Automated web scraper and continuous monitoring system using REST API for finding available appointments at ITV Argentona (Applus+) with Discord notifications.

**Target Portal**: https://aibs.appluscorp.com/?MenuActivo=mrNuevaReserva
**Station**: ITV Argentona (B08), Barcelona
**API Documentation**: See `API_DOCUMENTATION.md` for complete endpoint details

## Core Architecture

### Three-Module System (Optimized)

1. **itv_scraper.py** - Core scraping engine (`ITVScraper` class)
   - Uses REST API endpoint directly (no HTML parsing)
   - Calls `/Reserva/GetFechasHorasDisponibles` for JSON responses
   - Simple 4-step navigation flow
   - Fast and reliable (416 KB JSON response with all availability data)

2. **itv_monitor.py** - Continuous monitoring service (`ITVMonitor` class)
   - Wraps the scraper with periodic checking logic
   - Change detection using MD5 hash comparison
   - State persistence via `monitor_state.json`
   - Only notifies on NEW appointments (deduplication)

3. **discord_notifier.py** - Notification system (`DiscordNotifier` class)
   - Discord webhook integration with rich embeds
   - Graceful fallback to terminal-only mode if webhook not configured
   - Methods for different notification types (new appointments, errors, monitor status)

### API-Based Scraper Flow

The scraper uses a simplified 4-step process:

1. **GET** `/Reserva/ReservarMatricula?language=es&AppCentro=B08&Matricula={plate}`
   - Extracts `guidSesion` (GUID required for all subsequent steps)

2. **GET** `/Reserva/NavegarAVistaSiguiente?guidSesion={guid}&actualViewName=Datos_Contacto`
   - Navigates to station selection

3. **GET** `/Reserva/NavegarAVistaSiguiente?guidSesion={guid}&actualViewName=Eleccion_Estacion`
   - Navigates to dates page

4. **GET** `/Reserva/GetFechasHorasDisponibles?guidSesion={guid}&mes={MM}&anyo={YYYY}`
   - **KEY API CALL** - Returns JSON with all availability data

### Key Technical Details

**API Endpoint**:
- URL: `/Reserva/GetFechasHorasDisponibles`
- Method: GET
- Parameters:
  - `guidSesion`: Session GUID (from step 1)
  - `mes`: Month in MM format (01-12)
  - `anyo`: Year in YYYY format
- Response: JSON (~416 KB) with complete availability data

**JSON Structure**:
```json
{
  "calendarioSePuedeIrAtras": false,
  "calendarioSePuedeIrAdelante": true,
  "dias": [
    {
      "FechaString": "2025-11-07",
      "Seleccionable": false,
      "horas": [
        {
          "Disponible": true,  // KEY FIELD
          "Hora": "09:00",
          "Precio": 40.6
        }
      ]
    }
  ]
}
```

**Extracting Available Appointments**:
```python
for dia in data['dias']:
    if dia['Seleccionable']:
        for hora in dia['horas']:
            if hora['Disponible']:
                # This is an available appointment
                print(f"{dia['FechaString']} {hora['Hora']} - {hora['Precio']}€")
```

**Session Management**:
- `guidSesion` extracted via regex: `guidSesion["\s=:]+([a-f0-9\-]{36})`
- Session maintained through GUID in query parameters
- No cookies required (GUID is sufficient)
- Lifetime: ~15-30 minutes (estimated)

**State Management**:
- Monitor saves state to `monitor_state.json`:
  - List of appointments
  - Timestamp of last check
  - License plate
- Hash-based change detection prevents duplicate notifications
- State persists across restarts

## Common Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config.example.env .env
# Edit .env with LICENSE_PLATE and optionally DISCORD_WEBHOOK_URL
```

### Running

```bash
# Single scrape (for testing/debugging)
python itv_scraper.py

# Continuous monitoring (production use)
python itv_monitor.py

# Test Discord webhook
python discord_notifier.py
```

### Development

```bash
# Test scraper with custom license plate
# Edit itv_scraper.py main() function to change license_plate

# Check monitor state
cat monitor_state.json

# Clean generated files
rm -f monitor_state.json api_response_*.json http_log_*.txt http_summary_*.json
```

## Configuration

Environment variables in `.env`:

- `LICENSE_PLATE` - Vehicle license plate (required, no spaces/dashes, uppercase)
- `DISCORD_WEBHOOK_URL` - Discord webhook URL (optional, falls back to terminal-only)
- `MONITOR_INTERVAL_MINUTES` - Check interval in minutes (default: 5)

## Important Implementation Notes

### Advantages of API-Based Approach

✅ **JSON Response**: No HTML parsing needed, easy to process
✅ **Structured Data**: Complete information (dates, times, prices, discounts)
✅ **Fast**: Only 4 HTTP requests to get all months' availability
✅ **Reliable**: Not dependent on HTML/CSS structure changes
✅ **Complete**: Gets ALL available slots for entire months (not just visible dates)

### When API Structure Changes

If the scraper fails:

1. Run `python itv_scraper.py` to test the flow
2. Check if the API endpoint changed (unlikely)
3. Verify JSON structure in `api_response_*.json`
4. Update `_extract_available_appointments()` if JSON format changed
5. See `API_DOCUMENTATION.md` for complete endpoint specification

### Monitor Change Detection

The monitor in itv_monitor.py uses two-level detection:
1. **Hash comparison** - MD5 of entire appointments list
2. **Item comparison** - Individual appointment `fecha_hora` matching

This prevents:
- Duplicate notifications for same appointments
- Notifications when appointments are removed (not added)
- False positives from minor data changes

### Responsible Usage

- Default interval: 5 minutes (reasonable for the server)
- API returns 400+ KB JSON per month request
- Avoid intervals < 1 minute
- For multiple months: requests are sequential (months_ahead parameter)

## File Locations

- `itv_scraper.py` - Main scraper class
- `itv_monitor.py` - Continuous monitoring
- `discord_notifier.py` - Notification system
- `monitor_state.json` - Last known appointments and check time
- `api_response_*.json` - API responses (generated during testing)
- `.env` - User configuration (gitignored, contains license plate)
- `API_DOCUMENTATION.md` - Complete API endpoint documentation

## Code Structure

### itv_scraper.py
- `ITVScraper` class:
  - `__init__(license_plate)`: Initialize scraper
  - `_get_guid_sesion()`: Get session GUID (step 1)
  - `_navigate_to_dates_page()`: Navigate through flow (steps 2-3)
  - `get_available_dates(month, year, months_ahead)`: Get appointments (step 4)
  - `_extract_available_appointments(data)`: Parse JSON response
  - `close()`: Cleanup

### itv_monitor.py
- `ITVMonitor` class:
  - `__init__(...)`: Initialize monitor with config
  - `_load_state()` / `_save_state()`: State persistence
  - `_get_appointments_hash()`: Calculate MD5 for comparison
  - `_detect_new_appointments()`: Compare with previous state
  - `check_once()`: Single check execution
  - `start()`: Continuous monitoring loop

### discord_notifier.py
- `DiscordNotifier` class:
  - `__init__(webhook_url)`: Initialize notifier
  - `send_notification()`: Generic notification sender
  - `send_new_appointments()`: Specific for new appointments
  - `send_error()`: Error notifications
  - `send_monitor_started()`: Startup notification
  - `send_test()`: Test webhook

## Testing

### Test Scraper
```python
from itv_scraper import ITVScraper

scraper = ITVScraper(license_plate="3332FSS")  # Test plate
appointments = scraper.get_available_dates(months_ahead=1)
print(f"Found {len(appointments)} appointments")
scraper.close()
```

### Test Monitor (Single Check)
```python
from itv_monitor import ITVMonitor

monitor = ITVMonitor("3332FSS", discord_webhook_url=None)
appointments = monitor.check_once()
```

### Test Discord Notifier
```bash
python discord_notifier.py
```

## Troubleshooting

### Error: "No se pudo obtener guidSesion"
- The initial request failed or the response format changed
- Check if https://aibs.appluscorp.com is accessible
- Verify license plate format (no spaces, uppercase)

### Error: HTTP 500 on API call
- The guidSesion expired or is invalid
- Navigation flow was not completed correctly
- License plate might have an existing reservation blocking new queries
- Solution: Restart from step 1 (scraper does this automatically)

### No appointments found but website shows availability
- API might have changed structure
- Check `api_response_*.json` to see actual JSON
- Verify `dia['Seleccionable']` and `hora['Disponible']` fields
- Update extraction logic in `_extract_available_appointments()`

### Discord notifications not working
- Verify `DISCORD_WEBHOOK_URL` in `.env` is correct
- Test webhook with: `python discord_notifier.py`
- Check webhook URL hasn't expired in Discord settings
- Monitor falls back to terminal-only mode if webhook fails

## API Changelog

- **2025-11-07**: Initial implementation using discovered REST API endpoint
  - Direct API access via `/Reserva/GetFechasHorasDisponibles`
  - JSON responses with complete availability data
  - Simplified flow (4 steps instead of 5 HTML navigation)
  - No HTML parsing required

## Dependencies

- `requests`: HTTP client for API calls
- `beautifulsoup4`: Not used (kept in requirements for compatibility)
- `python-dotenv`: Environment variable management

## Security Notes

- License plates are personal data - never commit `.env` file
- Discord webhook URLs should be kept private
- No sensitive data is logged or stored except in `monitor_state.json`
- GUID sessions expire automatically (no cleanup needed)
