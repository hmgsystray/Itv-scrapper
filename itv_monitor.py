#!/usr/bin/env python3
"""
ITV Monitor - Monitoriza múltiples matrículas ITV simultáneamente
Cada matrícula está vinculada a una estación ITV específica
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from itv_scraper import ITVScraper
from discord_notifier import DiscordNotifier


class ITVMonitor:
    """
    Monitor que revisa múltiples matrículas (cada una en su estación asignada)
    """

    def __init__(self, plates_config: List[Dict[str, str]],
                 discord_webhook_url: Optional[str] = None,
                 interval_minutes: int = 5, days_limit: int = 15):
        """
        Inicializa el monitor multi-matrícula

        Args:
            plates_config: Lista de configuraciones de matrícula, cada una con:
                           {'plate': 'XXXXX', 'station': 'BXX', 'name': 'Descripción'}
            discord_webhook_url: URL del webhook de Discord (opcional)
            interval_minutes: Intervalo entre revisiones en minutos
            days_limit: Solo notificar citas dentro de los próximos N días
        """
        self.plates_config = plates_config
        self.interval_minutes = interval_minutes
        self.days_limit = days_limit

        # Notificador
        self.notifier = DiscordNotifier(discord_webhook_url)

        # State tracking - por matrícula
        self.last_appointments: Dict[str, List[Dict]] = {}
        self.scrapers: Dict[str, ITVScraper] = {}

        # Flag para enviar resumen inicial
        self.is_first_run = True

        # Métricas
        self.total_checks = 0
        self.successful_checks = 0
        self.failed_checks = 0

        # Cargar nombres de estaciones
        self.station_names = self._load_station_names()

        print(f"[INFO] ITV Monitor inicializado")
        print(f"  Matrículas: {len(self.plates_config)}")
        for config in self.plates_config:
            plate = config['plate']
            station = config['station']
            name = config.get('name', self.station_names.get(station, station))
            print(f"    - {plate} @ {station}: {name}")

    def _load_station_names(self) -> Dict[str, str]:
        """Carga nombres de estaciones desde stations.json"""
        try:
            if os.path.exists('stations.json'):
                with open('stations.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {s['code']: s['name'] for s in data.get('stations', [])}
        except Exception as e:
            print(f"[WARNING] Could not load station names: {e}")
        return {}

    def check_once(self) -> Dict[str, List[Dict]]:
        """
        Realiza una revisión de todas las matrículas

        Returns:
            Dict[str, List[Dict]]: Citas por matrícula
        """
        print("\n" + "="*70)
        print(f"Revisión iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        all_results = {}
        new_appointments_found = False

        for config in self.plates_config:
            plate = config['plate']
            station = config['station']
            station_name = config.get('name', self.station_names.get(station, station))

            print(f"\n--- Revisando {plate} @ {station}: {station_name} ---")

            try:
                # Crear o reutilizar scraper para esta matrícula
                if plate not in self.scrapers:
                    self.scrapers[plate] = ITVScraper(
                        license_plate=plate,
                        station_code=station
                    )

                scraper = self.scrapers[plate]

                # Buscar citas
                appointments = scraper.get_available_dates(
                    days_limit=self.days_limit,
                    reuse_guid=True
                )

                all_results[plate] = appointments

                print(f"  [OK] {len(appointments)} citas encontradas para {plate}")

                # En el primer run, enviar resumen de todas las matrículas
                if self.is_first_run:
                    print(f"  [RESUMEN INICIAL] Enviando estado inicial para {plate}")
                    self._notify_initial_status(plate, station, station_name, appointments)
                else:
                    # Detectar nuevas citas en runs posteriores
                    if self._has_new_appointments(plate, appointments):
                        new_appointments = self._get_new_appointments(plate, appointments)
                        if new_appointments:
                            print(f"  [NUEVO] {len(new_appointments)} nuevas citas para {plate}!")
                            self._notify_new_appointments(plate, station, station_name, new_appointments)
                            new_appointments_found = True

                # Actualizar estado
                self.last_appointments[plate] = appointments
                self.successful_checks += 1

            except Exception as e:
                print(f"  [ERROR] Error para {plate}: {type(e).__name__}: {e}")
                all_results[plate] = []
                self.failed_checks += 1

        self.total_checks += 1

        # Marcar que ya no es el primer run
        if self.is_first_run:
            self.is_first_run = False
            print(f"\n[INFO] Resumen inicial enviado. A partir de ahora solo se notificarán cambios.")

        # Resumen
        total_appointments = sum(len(apts) for apts in all_results.values())
        print(f"\n{'='*70}")
        print(f"Resumen: {total_appointments} citas totales en {len(self.plates_config)} matrículas")
        print(f"{'='*70}")

        return all_results

    def _has_new_appointments(self, plate: str, current_appointments: List[Dict]) -> bool:
        """Verifica si hay nuevas citas para una matrícula"""
        if plate not in self.last_appointments:
            return len(current_appointments) > 0

        previous_set = {apt['fecha_hora'] for apt in self.last_appointments[plate]}
        current_set = {apt['fecha_hora'] for apt in current_appointments}

        return len(current_set - previous_set) > 0

    def _get_new_appointments(self, plate: str, current_appointments: List[Dict]) -> List[Dict]:
        """Obtiene las citas nuevas (no vistas antes)"""
        if plate not in self.last_appointments:
            return current_appointments

        previous_set = {apt['fecha_hora'] for apt in self.last_appointments[plate]}
        return [apt for apt in current_appointments if apt['fecha_hora'] not in previous_set]

    def _notify_initial_status(self, plate: str, station_code: str, station_name: str, appointments: List[Dict]):
        """Envía notificación del estado inicial de una matrícula"""
        if len(appointments) > 0:
            # Tiene citas disponibles
            self.notifier.send_new_appointments(
                appointments=appointments,
                show_license_plate=False,
                license_plate=plate,
                station_code=station_code,
                station_name=station_name
            )
        else:
            # No tiene citas disponibles - enviar notificación informativa
            message = f"**{station_name}** ({station_code})\n\n"
            message += f"❌ No hay citas disponibles en los próximos {self.days_limit} días"
            self.notifier.send_notification(
                title="Monitor Iniciado - Sin citas",
                description=message,
                color=0x808080  # Gris
            )

    def _notify_new_appointments(self, plate: str, station_code: str, station_name: str, appointments: List[Dict]):
        """Envía notificación de nuevas citas"""
        self.notifier.send_new_appointments(
            appointments=appointments,
            show_license_plate=False,
            license_plate=plate,
            station_code=station_code,
            station_name=station_name
        )

    def start(self):
        """Inicia el monitor continuo"""
        print("\n" + "="*70)
        print("  ITV MONITOR INICIADO")
        print("="*70)
        print(f"\nConfiguración:")
        print(f"  Matrículas: {len(self.plates_config)}")
        print(f"  Intervalo: {self.interval_minutes} minutos")
        print(f"  Días límite: {self.days_limit}")
        print(f"\nPresiona Ctrl+C para detener\n")

        iteration = 0

        try:
            while True:
                iteration += 1
                print(f"\n{'='*70}")
                print(f"Iteración #{iteration}")

                self.check_once()

                # Esperar hasta la próxima revisión
                print(f"\nPróxima revisión en {self.interval_minutes} minutos...")
                time.sleep(self.interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\nMonitor detenido por el usuario")
            self._print_metrics()
            self._cleanup()
            print("\n¡Hasta pronto!")

        except Exception as e:
            print(f"\n[ERROR] Error crítico: {str(e)}")
            import traceback
            traceback.print_exc()
            self._print_metrics()
            self._cleanup()

    def _print_metrics(self):
        """Imprime métricas del monitor"""
        if self.total_checks > 0:
            success_rate = (self.successful_checks / (self.total_checks * len(self.plates_config))) * 100
            print(f"\n{'='*70}")
            print("MÉTRICAS DEL MONITOR")
            print(f"{'='*70}")
            print(f"  Total de revisiones: {self.total_checks}")
            print(f"  Checks exitosos: {self.successful_checks}")
            print(f"  Checks fallidos: {self.failed_checks}")
            print(f"  Tasa de éxito: {success_rate:.1f}%")
            print(f"{'='*70}")

    def _cleanup(self):
        """Limpia recursos"""
        for scraper in self.scrapers.values():
            scraper.close()
        print("[INFO] Recursos limpiados")


def main():
    """Función principal"""
    load_dotenv()

    # Leer configuración de estaciones desde .env
    stations_str = os.getenv("STATIONS", "")
    if not stations_str:
        print("[ERROR] No hay estaciones configuradas en STATIONS en .env")
        print("[INFO] Formato: STATIONS=B08:6784BDR,B07:6146CXR")
        print("[INFO] Usa CODIGO: para generar matrícula aleatoria")
        print("[INFO] Ejemplo: STATIONS=B08:,B07:,B01:")
        return

    # Parsear configuración de estaciones (formato: B08:6784BDR,B07:)
    plates_config = []
    for entry in stations_str.split(","):
        entry = entry.strip()
        if not entry:
            continue

        if ":" not in entry:
            print(f"[WARNING] Formato incorrecto: '{entry}'. Usa CODIGO:MATRICULA")
            continue

        station_code, plate = entry.split(":", 1)
        station_code = station_code.strip().upper()
        plate = plate.strip().upper()

        # Si no hay matrícula, generar una aleatoria
        if not plate:
            from itv_scraper import generate_random_license_plate
            plate = generate_random_license_plate()
            print(f"[INFO] Generada matrícula aleatoria {plate} para estación {station_code}")

        plates_config.append({
            'plate': plate,
            'station': station_code,
            'name': f'ITV {station_code}'
        })

    if not plates_config:
        print("[ERROR] No se encontraron estaciones válidas en STATIONS")
        return

    # Configuración opcional desde .env
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    interval = int(os.getenv("MONITOR_INTERVAL_MINUTES", "5"))
    days_limit = int(os.getenv("DAYS_LIMIT", "45"))

    # Crear y ejecutar monitor
    monitor = ITVMonitor(
        plates_config=plates_config,
        discord_webhook_url=discord_webhook if discord_webhook else None,
        interval_minutes=interval,
        days_limit=days_limit
    )

    monitor.start()


if __name__ == "__main__":
    main()
