# Ascoltatore wallbox senza privilegi: TCP 8080 (verifica app) + UDP 7090 (KEBA).
# La porta 502 (Modbus, privilegiata) si aggiunge dopo, solo se serve.
import socket, threading, time
LOG = open("tools/wallbox_bg.log", "a")
def log(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True); LOG.write(line+"\n"); LOG.flush()
def handle(c, a, port):
    log(f"[TCP {port}] CONNESSO da {a[0]}:{a[1]}  <-- cerca la wallbox!")
    c.settimeout(40)
    try:
        while True:
            d = c.recv(1024)
            if not d: break
            t = d.decode('ascii','replace').replace('\r',' ').replace('\n',' ').strip()
            log(f"[TCP {port}] <- hex={d.hex()} testo={t!r}")
    except Exception as e: log(f"[TCP {port}] {e}")
    finally: c.close(); log(f"[TCP {port}] chiuso {a[0]}")
def tcp(port):
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("0.0.0.0",port)); s.listen(5); log(f"[TCP {port}] in ascolto")
    while True:
        c,a=s.accept(); threading.Thread(target=handle,args=(c,a,port),daemon=True).start()
def udp():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("0.0.0.0",7090)); log("[UDP 7090] in ascolto")
    while True:
        d,a=s.recvfrom(2048)
        log(f"[UDP 7090] da {a[0]}: {d.decode('ascii','replace').strip()!r} hex={d.hex()}")
log("=== ascoltatore wallbox (bg) avviato ===")
threading.Thread(target=udp,daemon=True).start()
tcp(8080)
