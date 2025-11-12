#!/usr/bin/env python3
"""
Notificador de Discord para el monitor de ITV
Envía notificaciones mediante webhooks de Discord
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional


class DiscordNotifier:
    """Clase para enviar notificaciones a Discord o terminal"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Inicializa el notificador

        Args:
            webhook_url: URL del webhook de Discord (opcional)
                        Si es None, solo muestra por terminal
        """
        self.webhook_url = webhook_url
        self.terminal_only = webhook_url is None or webhook_url == ""

    def send_notification(self, title: str, description: str,
                         color: int = 0x00ff00, fields: Optional[List[Dict]] = None) -> bool:
        """
        Envía una notificación embed a Discord o terminal

        Args:
            title: Título del mensaje
            description: Descripción del mensaje
            color: Color del embed en hexadecimal
            fields: Lista de campos adicionales

        Returns:
            bool: True si se envió correctamente
        """
        # Modo terminal
        if self.terminal_only:
            # Remove emojis for Windows terminal compatibility
            title_clean = title.encode('ascii', 'ignore').decode('ascii')
            desc_clean = description.encode('ascii', 'ignore').decode('ascii') if description else ""

            print("\n" + "="*70)
            print(f">> {title_clean}")
            print("="*70)
            if desc_clean:
                print(desc_clean)
            if fields:
                print("\nDetalles:")
                for field in fields:
                    name = str(field.get('name', 'N/A')).encode('ascii', 'ignore').decode('ascii')
                    value = str(field.get('value', 'N/A')).encode('ascii', 'ignore').decode('ascii')
                    print(f"\n{name}:")
                    print(f"  {value}")
            print("="*70)
            return True

        # Modo Discord
        try:
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "ITV Scraper Monitor"
                }
            }

            if fields:
                embed["fields"] = fields

            data = {
                "embeds": [embed]
            }

            response = requests.post(
                self.webhook_url,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 204:
                print("[OK] Notificacion enviada a Discord")
                return True
            else:
                print(f"[AVISO] Error al enviar notificacion: {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] Error al enviar notificacion a Discord: {str(e)}")
            return False

    def send_new_appointments(self, appointments: List[Dict], show_license_plate: bool = False, license_plate: str = "",
                             station_code: str = "", station_name: str = "") -> bool:
        """
        Envía notificación de nuevas citas disponibles

        Args:
            appointments: Lista de citas disponibles
            show_license_plate: Si mostrar la matrícula en el mensaje (default: False)
            license_plate: Matrícula del vehículo (opcional)
            station_code: Código de la estación ITV (opcional, ej: "B08")
            station_name: Nombre de la estación ITV (opcional, ej: "ITV Argentona")

        Returns:
            bool: True si se envió correctamente
        """
        if not appointments:
            return False

        # URL base para reservar
        base_reservation_url = "https://aibs.appluscorp.com/?MenuActivo=mrNuevaReserva"

        # Agrupar por fecha
        appointments_by_date = {}
        for apt in appointments:
            fecha = apt['fecha']
            if fecha not in appointments_by_date:
                appointments_by_date[fecha] = []
            appointments_by_date[fecha].append(apt)

        fields = []
        for fecha, citas in sorted(appointments_by_date.items())[:10]:  # Max 10 fechas
            horas = [cita['hora'] for cita in citas[:5]]  # Max 5 horas por fecha
            horas_text = ", ".join(horas)
            if len(citas) > 5:
                horas_text += f" ... (+{len(citas)-5} más)"

            fields.append({
                "name": f"📅 {fecha}",
                "value": f"🕐 {horas_text}",
                "inline": False
            })

        # Construir título con información de estación si está disponible
        title = "🔔 NUEVAS CITAS DISPONIBLES"
        if station_name and station_code:
            title += f" en {station_name} ({station_code})"
        elif station_code:
            title += f" en estación {station_code}"

        description = f"Se han detectado **{len(appointments)} nueva(s) cita(s)** disponible(s)"

        if show_license_plate and license_plate:
            description += f" para la matrícula **{license_plate}**"

        description += "\n\n"

        if len(appointments_by_date) > 10:
            description += f"_(Mostrando las primeras 10 fechas de {len(appointments_by_date)})_\n\n"

        # Mostrar la primera cita con enlace directo
        primera_cita = appointments[0]
        description += f"**Primera cita disponible:** {primera_cita['fecha']} a las {primera_cita['hora']}\n\n"
        description += f"🔗 **[RESERVAR AHORA]({base_reservation_url})**"

        return self.send_notification(
            title=title,
            description=description,
            color=0x00ff00,  # Verde
            fields=fields
        )

    def send_no_appointments(self, show_license_plate: bool = False, license_plate: str = "",
                            station_code: str = "", station_name: str = "") -> bool:
        """
        Envía notificación de que no hay citas disponibles

        Args:
            show_license_plate: Si mostrar la matrícula en el mensaje (default: False)
            license_plate: Matrícula del vehículo (opcional)
            station_code: Código de la estación ITV (opcional, ej: "B08")
            station_name: Nombre de la estación ITV (opcional, ej: "ITV Argentona")

        Returns:
            bool: True si se envió correctamente
        """
        title = "No hay citas disponibles"
        if station_name and station_code:
            title += f" en {station_name} ({station_code})"
        elif station_code:
            title += f" en estación {station_code}"

        description = "No se encontraron citas disponibles"

        if show_license_plate and license_plate:
            description += f" para la matrícula **{license_plate}**"

        description += "\n\nEl monitor seguirá buscando..."

        return self.send_notification(
            title=title,
            description=description,
            color=0xffa500  # Naranja
        )

    def send_error(self, error_message: str) -> bool:
        """
        Envía notificación de error

        Args:
            error_message: Mensaje de error

        Returns:
            bool: True si se envió correctamente
        """
        title = "Error en el monitor"
        description = f"Se ha producido un error:\n```{error_message}```"

        return self.send_notification(
            title=title,
            description=description,
            color=0xff0000  # Rojo
        )

    def send_monitor_started(self, interval_minutes: int, days_limit: int = 15, show_license_plate: bool = False, license_plate: str = "") -> bool:
        """
        Envía notificación de que el monitor ha iniciado

        Args:
            interval_minutes: Intervalo de revisión en minutos
            days_limit: Número de días de anticipación para notificar
            show_license_plate: Si mostrar la matrícula en el mensaje (default: False)
            license_plate: Matrícula del vehículo (opcional)

        Returns:
            bool: True si se envió correctamente
        """
        title = "🚀 Monitor ITV iniciado"
        description = f"El monitor ha iniciado correctamente\n\n"

        if show_license_plate and license_plate:
            description += f"**Matrícula:** {license_plate}\n"

        description += f"**Intervalo:** {interval_minutes} minutos\n"
        description += f"**Notificar citas en:** próximos {days_limit} días\n\n"
        description += "Te avisaremos cuando encuentre citas disponibles 🔔"

        return self.send_notification(
            title=title,
            description=description,
            color=0x0099ff  # Azul
        )

    def send_test(self) -> bool:
        """
        Envía un mensaje de prueba

        Returns:
            bool: True si se envió correctamente
        """
        title = "Webhook de Discord funcionando"
        description = "Este es un mensaje de prueba del sistema de notificaciones."

        return self.send_notification(
            title=title,
            description=description,
            color=0x00ff00  # Verde
        )


def test_webhook():
    """Función para probar el webhook de Discord"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("[ERROR] No se ha configurado DISCORD_WEBHOOK_URL en el archivo .env")
        print("\nComo usar:")
        print("1. Ve a Discord > Ajustes del canal > Integraciones > Webhooks")
        print("2. Crea un nuevo webhook y copia la URL")
        print("3. Añade la URL al archivo .env: DISCORD_WEBHOOK_URL=https://...")
        return

    print("Probando webhook...")
    notifier = DiscordNotifier(webhook_url)

    if notifier.send_test():
        print("[OK] Webhook funcionando correctamente!")
    else:
        print("[ERROR] Error al enviar mensaje de prueba")


if __name__ == "__main__":
    test_webhook()
