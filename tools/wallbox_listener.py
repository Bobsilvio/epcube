"""Ascoltatore wallbox: scopre se il gateway EP Cube cerca davvero una KEBA.

Si finge una wallbox KEBA sulle porte che il gateway userebbe:
- TCP 502  (Modbus TCP): accetta la connessione, registra ogni richiesta e
  risponde in modo valido con registri a zero, così il gateway prosegue il
  dialogo e possiamo vedere TUTTI i registri che interroga;
- UDP 7090 (protocollo UDP KEBA): registra i pacchetti in arrivo.

Non modifica nulla sul gateway: ascolta e risponde solo per capire il protocollo.

Uso (TCP 502 è una porta privilegiata, serve sudo):

    sudo python3 tools/wallbox_listener.py

Nell'app EP Cube imposta la wallbox con IP manuale = IP di questo Mac
(192.168.178.132) e avvia la ricerca. Tutto finisce in tools/wallbox_listener.log.
Ferma con Ctrl+C.
"""

import socket
import threading
import time
from pathlib import Path

LOG = Path(__file__).with_name("wallbox_listener.log")
TCP_PORTS = (502, 8080)  # 502 = Modbus TCP, 8080 = verifica HTTP dall'app
UDP_PORT = 7090


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def modbus_reply(req: bytes) -> bytes | None:
    """Risposta Modbus-TCP valida a una lettura, con registri a zero."""
    if len(req) < 12:
        return None
    tid = req[0:2]
    unit = req[6]
    fn = req[7]
    if fn in (0x03, 0x04):  # read holding / input registers
        qty = int.from_bytes(req[10:12], "big")
        payload = bytes([unit, fn, qty * 2]) + b"\x00" * (qty * 2)
    elif fn in (0x06, 0x10):  # write single / multiple: eco dell'indirizzo
        payload = bytes([unit, fn]) + req[8:12]
    else:
        payload = bytes([unit, fn | 0x80, 0x01])  # exception illegal function
    return tid + b"\x00\x00" + len(payload).to_bytes(2, "big") + payload


def handle_tcp(conn: socket.socket, addr, port: int) -> None:
    log(f"[TCP {port}] CONNESSO da {addr[0]}:{addr[1]}  <-- qualcuno cerca la wallbox!")
    conn.settimeout(30)
    try:
        while True:
            data = conn.recv(512)
            if not data:
                break
            text = data.decode("ascii", "replace").replace("\r", " ").replace("\n", " ").strip()
            log(f"[TCP {port}] <- hex={data.hex()}  testo={text!r}")
            reply = modbus_reply(data) if port == 502 else None
            if reply:
                conn.sendall(reply)
                log(f"[TCP {port}] -> {reply.hex()}")
    except socket.timeout:
        log(f"[TCP {port}] timeout, chiudo")
    except OSError as e:
        log(f"[TCP {port}] errore: {e}")
    finally:
        conn.close()
        log(f"[TCP {port}] chiuso {addr[0]}")


def serve_tcp(port: int) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
    except PermissionError:
        log(f"[TCP {port}] permesso negato: lancia con sudo")
        return
    s.listen(5)
    log(f"[TCP {port}] in ascolto")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_tcp, args=(conn, addr, port), daemon=True).start()


def serve_udp() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", UDP_PORT))
    log(f"[UDP {UDP_PORT}] in ascolto")
    while True:
        data, addr = s.recvfrom(1024)
        text = data.decode("ascii", "replace").strip()
        log(f"[UDP 7090] da {addr[0]}: {text!r}  hex={data.hex()}")
        # KEBA UDP risponde ai comandi testuali "i", "report N": qui solo log
        if data.strip() in (b"i", b"I"):
            s.sendto(b'"Firmware":"emulatore"', addr)


if __name__ == "__main__":
    log("=== avvio ascoltatore wallbox ===")
    threading.Thread(target=serve_udp, daemon=True).start()
    for p in TCP_PORTS[1:]:
        threading.Thread(target=serve_tcp, args=(p,), daemon=True).start()
    try:
        serve_tcp(TCP_PORTS[0])
    except KeyboardInterrupt:
        log("=== fermato ===")
