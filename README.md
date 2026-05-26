<div align="center">
    <h1>Self Checkout</h1>
    <p>RFID-powered autonomous retail checkout over MQTT</p>
</div>

Scan product tags at the shelf, stream them through a message broker, and consume them anywhere on the network — without wiring every device directly to your server.

### What is Self Checkout?

Self Checkout is a small system for **reading UHF RFID tags** and moving that data over **MQTT** as JSON. A USB reader on a PC (or edge device) polls tags; subscribers receive stable EPC identifiers in real time.

```
rfid/read                       # MQTT topic for tag scans
{"tags": ["E2806915000040"]}    # JSON payload
```

Typical flow: a **scanner** reads tags from serial (`/dev/ttyUSB0`), publishes to the broker, and a **store client** (or your own service) subscribes and acts on the cart — print, persist, or trigger checkout logic.

Traditional setups often couple the reader straight into one app. Here the reader, broker, and consumers are separate. You can run the broker on a Pi, the scanner at the shelf, and multiple listeners (inventory, display, checkout) on the same topic.

## Architecture

```text
  RFID reader (USB)     MQTT broker (amqtt)       Subscribers
        |                      |                      |
        |  serial              |  rfid/read           |
        v                      v                      v
  scanner/server.py  ----->  localhost:1883  ----->  store/client.py
```

| Component | Path | Role |
| --------- | ---- | ---- |
| Scanner | `scanner/read.py` | Serial protocol, frame parsing, EPC extraction |
| Publisher | `scanner/server.py` | Polls tags and publishes JSON |
| Consumer | `store/client.py` | Subscribes and prints tag IDs |

Runs on **Python 3.12.7** with **[uv](https://github.com/astral-sh/uv)** as the package manager.

## Local development setup

### Clone the repository

```bash
git clone https://github.com/mrcingo/self-checkout.git
cd self-checkout
```

### Install dependencies

```bash
uv sync
```

### Run the stack

Use **three terminals** from the project root.

**1 — Start the MQTT broker**

```bash
uv run amqtt
```

**2 — Start the store client (subscriber)**

```bash
uv run python store/client.py
```

**3 — Start the scanner (publisher)**

Requires an RFID reader on serial. On Linux/WSL, attach the USB device and set the port if needed:

```bash
export RFID_PORT=/dev/ttyUSB0
cd scanner && uv run python server.py
```

When tags are in range, the client terminal prints one EPC per line:

```text
Listening on rfid/read (localhost:1883)
E2806915000040
E2806915000050
```

### Test the reader without MQTT

```bash
cd scanner && uv run python read.py
```

## Configuration

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `RFID_PORT` | `/dev/ttyUSB0` | Serial port for the RFID module |
| `RFID_BAUDRATE` | `115200` | Serial baud rate |
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `rfid/read` | Topic for tag JSON payloads |

On WSL2, pass the USB reader through with [usbipd-win](https://github.com/dorssel/usbipd-win) and add your user to the `dialout` group for serial access.

## Project layout

```text
scanner/
  read.py          # RfidReader API (serial + frame parsing)
  server.py        # Read tags and publish to MQTT
store/
  client.py        # Subscribe to rfid/read and print tags
pyproject.toml     # Dependencies (amqtt, paho-mqtt, pyserial)
AGENTS.md          # Notes for AI agents working in this repo
```

## Stack

- **[amqtt](https://github.com/Yakifo/amqtt)** — embedded MQTT 3.1.1 broker
- **[paho-mqtt](https://pypi.org/project/paho-mqtt/)** — Python MQTT clients
- **[pyserial](https://pypi.org/project/pyserial/)** — USB/serial RFID reader

## License

See [LICENSE](LICENSE).
