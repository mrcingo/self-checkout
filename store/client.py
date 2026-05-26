"""Subscribe to RFID reads from MQTT and print them."""

from __future__ import annotations

import json
import os
import sys

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "rfid/read")


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)
        print(f"Listening on {MQTT_TOPIC} ({MQTT_HOST}:{MQTT_PORT})")
    else:
        print("Connect failed:", reason_code)


def on_message(
    client: mqtt.Client,
    userdata: object,
    msg: mqtt.MQTTMessage,
) -> None:
    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print("invalid JSON:", msg.payload.decode())
        return

    tags = data.get("tags", [])
    if not tags:
        print("(no tags)")
        return

    for tag in tags:
        print(tag)


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_forever()


if __name__ == "__main__":
    main()
    sys.exit(0)
