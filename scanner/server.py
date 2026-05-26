"""Read RFID tags from serial and publish them as JSON over MQTT."""

from __future__ import annotations

import json
import os
import signal
import sys

import paho.mqtt.client as mqtt

from read import RfidReader

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "rfid/read")


def publish_tags(client: mqtt.Client, tags: list[str]) -> None:
    payload = json.dumps({"tags": tags})
    client.publish(MQTT_TOPIC, payload)
    print(f"published to {MQTT_TOPIC}: {payload}")


def run() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    stop = False

    def on_signal(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    try:
        with RfidReader() as reader:
            while not stop:
                tags = reader.poll()
                if tags:
                    publish_tags(client, tags)
    finally:
        client.loop_stop()
        client.disconnect()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
    sys.exit(0)
