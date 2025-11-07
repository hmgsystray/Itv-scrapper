#!/usr/bin/env python3
"""
Módulo para enviar notificaciones a Discord mediante webhook
"""

import requests
import json
from datetime import datetime


class DiscordNotifier:
    """Clase para enviar notificaciones a Discord"""

    def __init__(self, webhook_url):
        """
        Inicializa el notificador de Discord

        Args:
            webhook_url (str): URL del webhook de Discord
        """
        self.webhook_url = webhook_url

    def send_notification(self, title, description, color=0x00ff00, fields=None):
        """
        Envía una notificación embed a Discord

        Args:
            title (str): Título del mensaje
            description (str): Descripción del mensaje
            color (int): Color del embed en hexadecimal
            fields (list): Lista de campos adicionales

        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "ITV Argentona Monitor"
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
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 204:
                print("✓ Notificación enviada a Discord")
                return True
            else:
                print(f"⚠️  Error al enviar notificación: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error al enviar notificación a Discord: {str(e)}")
            return False

    def send_new_appointments(self, appointments, license_plate):
        """
        Envía notificación de nuevas citas disponibles

        Args:
            appointments (list): Lista de citas disponibles
            license_plate (str): Matrícula del vehículo

        Returns:
            bool: True si se envió correctamente
        """
        if not appointments:
            return False

        fields = []
        for i, apt in enumerate(appointments[:10], 1):  # Máximo 10 citas
            text = apt.get('text', 'N/A')
            fields.append({
                "name": f"Cita #{i}",
                "value": text[:1024],  # Discord limita a 1024 caracteres por field
                "inline": False
            })

        title = "🚗 ¡Nuevas citas disponibles en ITV Argentona!"
        description = f"Se han detectado **{len(appointments)} cita(s) disponible(s)** para la matrícula **{license_plate}**\n\n"

        if len(appointments) > 10:
            description += f"_(Mostrando las primeras 10 de {len(appointments)})_\n"

        description += "**¡Reserva ahora!** 👉 https://aibs.appluscorp.com/"

        return self.send_notification(
            title=title,
            description=description,
            color=0x00ff00,  # Verde
            fields=fields
        )

    def send_no_appointments(self, license_plate):
        """
        Envía notificación de que no hay citas disponibles

        Args:
            license_plate (str): Matrícula del vehículo

        Returns:
            bool: True si se envió correctamente
        """
        title = "ℹ️ No hay citas disponibles"
        description = f"No se encontraron citas disponibles para la matrícula **{license_plate}**\n\n"
        description += "El monitor seguirá buscando..."

        return self.send_notification(
            title=title,
            description=description,
            color=0xffa500  # Naranja
        )

    def send_error(self, error_message):
        """
        Envía notificación de error

        Args:
            error_message (str): Mensaje de error

        Returns:
            bool: True si se envió correctamente
        """
        title = "❌ Error en el monitor"
        description = f"Se ha producido un error:\n```{error_message}```"

        return self.send_notification(
            title=title,
            description=description,
            color=0xff0000  # Rojo
        )

    def send_monitor_started(self, license_plate, interval_minutes):
        """
        Envía notificación de que el monitor ha iniciado

        Args:
            license_plate (str): Matrícula del vehículo
            interval_minutes (int): Intervalo de revisión en minutos

        Returns:
            bool: True si se envió correctamente
        """
        title = "🟢 Monitor iniciado"
        description = f"El monitor de ITV Argentona ha iniciado correctamente\n\n"
        description += f"**Matrícula:** {license_plate}\n"
        description += f"**Intervalo de revisión:** {interval_minutes} minutos\n\n"
        description += "Te notificaremos cuando haya citas disponibles."

        return self.send_notification(
            title=title,
            description=description,
            color=0x0099ff  # Azul
        )

    def send_test(self):
        """
        Envía un mensaje de prueba

        Returns:
            bool: True si se envió correctamente
        """
        title = "✅ Webhook de Discord funcionando"
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
        print("❌ Error: No se ha configurado DISCORD_WEBHOOK_URL en el archivo .env")
        return

    print(f"🔗 Probando webhook...")
    notifier = DiscordNotifier(webhook_url)

    if notifier.send_test():
        print("✅ ¡Webhook funcionando correctamente!")
    else:
        print("❌ Error al enviar mensaje de prueba")


if __name__ == "__main__":
    test_webhook()
