# AGENTS.md — self-checkout

Authoritative guidance for AI agents working in this repository. Read this before changing code or suggesting architecture.

## Project

**self-checkout** is an RFID + MQTT autonomous retail checkout system. Tags are read from a UHF reader over USB serial, published as JSON on MQTT, and consumed by store-side services (cart, inventory, checkout).

**Roadmap (not all implemented yet):** ESP32 proximity triggers, persistent cart storage, dedicated `broker/` entrypoint, multi-store topic hierarchy. Do not build roadmap items unless the user asks.

| Item | Version / tool |
| ---- | -------------- |
| Python | 3.12.7 (`.python-version`, `pyproject.toml`) |
| Package manager | [uv](https://github.com/astral-sh/uv) — `uv sync`, `uv run` |
| Formatter | Black, line length 88 — `uv run black .` on touched Python |
| MQTT broker (dev) | `uv run amqtt` (CLI) or future `broker/main.py` |
| MQTT clients | paho-mqtt 2.x |
| RFID serial | pyserial |

Pinned versions: `uv.lock`. Prefer `uv.lock` / `pyproject.toml` over memory.

Also follow workspace rules in `.cursor/rules/karpathy-guidelines.mdc` (simplicity, surgical diffs, ask when unclear).

---

## Agent conventions (required)

1. **Do nothing more than asked** — no extra endpoints, refactors, tests, or docs unless requested.
2. **Minimal diffs** — match existing style; run `uv run black .` on touched Python.
3. **No git commits** unless the user explicitly asks.
4. **Library boundaries:**
   - **amqtt** — broker only (`broker/` or documented CLI). Asyncio. Never use for app clients.
   - **paho-mqtt** — publishers/subscribers (`scanner/server.py`, `store/`, future `store/store.py`).
   - **pyserial** — RFID hardware only (`scanner/read.py`). Never mix asyncio broker code into serial modules.
5. **Do not** use deprecated **hbmqtt**; this project targets **amqtt 0.11.x** (rename from hbmqtt, not drop-in).
6. **Topics** — hierarchical names, no leading slash by default (e.g. `rfid/read`, `store/{id}/cart/events`). Document new topics in code and README.
7. **Uncertainty** — re-fetch canonical MQTT docs (below) or read existing modules before inventing APIs.
8. **Imports in `scanner/`** — `server.py` currently uses `from read import RfidReader` and is meant to run as `cd scanner && uv run python server.py`. If adding packages, prefer fixing to package imports (`from scanner.read import …`) only when the user wants that refactor.
9. **User-facing docs** — keep `README.md` in sync when changing run commands, env vars, or layout.

---

## Architecture

```text
  UHF RFID module (USB serial)          MQTT broker              Consumers
           |                                 |                        |
           |  AA/DD frames, 115200           |  topic: rfid/read      |
           v                                 v                        v
    scanner/read.py  -->  scanner/server.py  ------>  store/client.py
    (RfidReader)          (JSON publish)              (subscribe/print)
```

**Separation of concerns**

| Layer | Responsibility | Must not |
| ----- | -------------- | -------- |
| `scanner/read.py` | Serial I/O, frame parse, EPC strings | MQTT, business logic |
| `scanner/server.py` | Poll reader, publish MQTT | SQL, HTTP, cart rules |
| `store/client.py` | Subscribe, handle payloads | Serial / RFID driver |
| Broker | Route messages only | Store cart data (unless explicitly adding persistence there) |

---

## Repository layout (current)

```text
scanner/
  read.py       # RfidReader, RfidConfig, frame parsing (public API for hardware)
  server.py     # MQTT publisher loop
store/
  client.py     # MQTT subscriber (prints tags today)
broker/         # (optional) amqtt programmatic broker — not in tree yet; use `uv run amqtt`
pyproject.toml
uv.lock
README.md       # Human setup & run instructions
AGENTS.md       # This file
```

---

## MQTT message contract

**Topic (default):** `rfid/read`  
**Publisher:** `scanner/server.py`  
**Subscriber:** `store/client.py` (and any new store services)

**Payload (UTF-8 JSON):**

```json
{"tags": ["E2806915000040", "E2806915000050"]}
```

- `tags`: array of uppercase hex EPC strings (stable tail, see RFID section).
- Publish only when `poll()` returns a non-empty list (no empty publishes today).
- QoS 0 unless the user requests otherwise.

**Environment (shared by scanner + store):**

| Variable | Default | Used by |
| -------- | ------- | ------- |
| `MQTT_HOST` | `localhost` | server, client |
| `MQTT_PORT` | `1883` | server, client |
| `MQTT_TOPIC` | `rfid/read` | server, client |
| `RFID_PORT` | `/dev/ttyUSB0` | `scanner/read.py` |
| `RFID_BAUDRATE` | `115200` | `scanner/read.py` |
| `RFID_SCAN_TIME` | `30` (`0x1E`) | inventory command byte |
| `RFID_EPC_HEX_LEN` | `16` | chars kept from raw slice (drops noisy prefix) |
| `RFID_SERIAL_TIMEOUT` | `1` | serial read timeout (seconds) |

---

## RFID / `scanner/read.py`

Hardware: UHF reader module on USB serial (CH340 etc. → `/dev/ttyUSB0` on Linux). **Not** the Raspberry Pi Pico; Pico is `/dev/ttyACM0` and separate (MicroPython / mpremote).

**Protocol (do not change without user + hardware validation):**

- Frames: `0xAA` header … payload … checksum … `0xDD` end.
- Inventory command: `build_scan_command(scan_time)` — byte `0x22` inventory, default `scan_time=0x1E`.
- No-tag responses: `frame[2] == 0xFF` — skip, do not print.
- EPC extraction: bytes `frame[3:15]` → hex → keep last `RFID_EPC_HEX_LEN` chars (stable ID; leading bytes are RSSI/noise in practice).

**Public API (reuse, do not duplicate):**

```python
from read import RfidReader, RfidConfig  # when cwd is scanner/
# Intended surface:
#   RfidConfig          — dataclass, env-backed defaults
#   build_scan_command  — raw command bytes
#   extract_frame       — streaming parser
#   epc_from_frame      — single-frame EPC or None
#   parse_frames        — (tags, remainder_buffer)
#   RfidReader          — context manager; .poll() -> list[str]; .iter_tags()
```

**Run scanner without MQTT:**

```bash
cd scanner && uv run python read.py
```

---

## Local development (verify changes)

Three terminals from repo root:

```bash
# 1 — broker
uv run amqtt

# 2 — consumer
uv run python store/client.py

# 3 — publisher (needs RFID USB + WSL passthrough if applicable)
export RFID_PORT=/dev/ttyUSB0
cd scanner && uv run python server.py
```

**CLI smoke test (no Python app code):**

```bash
uv run amqtt_sub --url mqtt://localhost -t rfid/read
uv run amqtt_pub --url mqtt://localhost -t rfid/read -m '{"tags":["TEST"]}'
```

---

## Hardware & WSL2

- **WSL2:** USB serial devices are not visible until attached from Windows (`usbipd list` / `usbipd attach --wsl`).
- **Permissions:** user must be in `dialout` for `/dev/ttyUSB*`.
- **One process per port** — stop `scanner/server.py` before `mpremote` or other serial tools on the same device.
- **Power:** UHF modules can brown out on weak USB hubs; mention if reads are flaky.
- **Antenna:** reader module drives the antenna; Pico cannot replace the UHF module without UART wiring.

---

## When to use which library

| Component | Library | Location / command |
| --------- | ------- | ------------------ |
| Broker (dev) | amqtt CLI | `uv run amqtt` |
| Broker (code) | amqtt | `broker/main.py` when added — asyncio only |
| Publishers / subscribers | paho-mqtt | `scanner/server.py`, `store/` |
| RFID serial | pyserial | `scanner/read.py` only |
| Local MQTT smoke tests | amqtt CLI | `amqtt_pub`, `amqtt_sub` |

Do **not** mix broker implementations.

---

## Authoritative MQTT documentation

When implementing or debugging MQTT, use these sources — not outdated HBMQTT/blog examples.

| Role | Library | Canonical docs |
| ---- | ------- | -------------- |
| Broker | amqtt | [amqtt/docs (`main`)](https://github.com/Yakifo/amqtt/tree/main/docs) · [Read the Docs](https://amqtt.readthedocs.io/) |
| Client | paho-mqtt | [client module](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) · [migrations 1.x→2.0](https://github.com/eclipse/paho.mqtt.python/blob/master/docs/migrations.rst) |

### Refreshing docs (agents)

```text
https://raw.githubusercontent.com/Yakifo/amqtt/main/docs/<file>.md
https://raw.githubusercontent.com/Yakifo/amqtt/main/amqtt/scripts/default_broker.yaml
https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
```

Key amqtt paths: `quickstart.md`, `docker.md`, `references/broker_config.md`.

---

## amqtt (broker) — essentials

### CLI

```bash
uv run amqtt
uv run amqtt_pub --url mqtt://localhost -t rfid/read -m '{"tags":["x"]}'
uv run amqtt_sub --url mqtt://localhost -t rfid/read
```

URL scheme: `[mqtt|ws][s]://[user:pass@]host[:port]`.

### Programmatic broker (when `broker/main.py` exists)

```python
import asyncio
from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig

async def main() -> None:
    broker = Broker(BrokerConfig())
    await broker.start()
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()

asyncio.run(main())
```

- Default: TCP `0.0.0.0:1883`, anonymous auth enabled.
- Production: configure plugins per [broker_config.md](https://github.com/Yakifo/amqtt/blob/main/docs/references/broker_config.md); do not rely on `allow_anonymous: false` alone.

### Docker (optional)

```bash
docker run -d -p 1883:1883 amqtt/amqtt:latest
```

---

## paho-mqtt (client) — essentials

**Always** use Callback API v2 for new code:

```python
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(host, port=1883)
client.loop_start()  # publisher background loop
# or client.loop_forever()  # blocking subscriber
```

### Callback API v2 (summary)

| Callback | v2 notes |
| -------- | -------- |
| `on_connect` | `reason_code` is `ReasonCode`; check `== 0` for success |
| `on_disconnect` | `reason_code == 0` = clean |
| `on_subscribe` / `on_unsubscribe` | `reason_codes` is a list |
| `on_message` | `(client, userdata, message)` — decode `message.payload` |

Compare `reason_code` to string names (e.g. `"Unsupported protocol version"`), not only numeric codes.

### Patterns in this repo

- **Publisher (`scanner/server.py`):** `loop_start()` → `publish()` in loop → `loop_stop()` on exit; handle SIGINT/SIGTERM.
- **Subscriber (`store/client.py`):** `on_connect` subscribes to `MQTT_TOPIC`; `on_message` parses JSON; `loop_forever()`.

Default protocol: MQTT v3.1.1. MQTT v5 only if explicitly requested.

---

## MQTT protocol reminders

- Wildcards: `+` (one level), `#` (rest; must be last).
- Ports: `1883` (MQTT), `8883` (TLS), WebSocket via `BrokerConfig.listeners`.
- External test broker: [test.amqtt.io](https://test.amqtt.io).

---

## Adding features (guidance)

| User asks for… | Likely location | Notes |
| -------------- | --------------- | ----- |
| Cart / DB / checkout rules | `store/store.py` or new `store/` modules | Subscribe to `rfid/read` or finer topics; no serial |
| Dedup / cooldown on tags | `scanner/server.py` or `read.py` | Keep hardware parsing in `read.py` |
| New MQTT event types | New topic + document in README | e.g. `store/{id}/cart/events` |
| HTTP API | New module, not in broker | Unless user wants broker plugin |
| Pico / ESP32 | Separate MicroPython tree or `devices/` | UART to RFID module; publish via MQTT from edge |

---

## Common mistakes (avoid)

- Using `localhost` on device B to reach a broker on device A — use LAN IP.
- Parsing `BB … 7E` frames while hardware speaks `AA … DD` (wrong protocol).
- Importing `RfidReader` from repo root without package layout — run from `scanner/` or fix packages deliberately.
- Adding `hbmqtt`, `mosquitto` client libs, or second broker stack.
- Publishing non-JSON or different schema without updating `store/client.py` and this contract.
