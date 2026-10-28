import socket, threading, time
LOG=open("tools/wallbox_8080.log","a")
def log(m):
    line=f"{time.strftime('%H:%M:%S')} {m}"; print(line,flush=True); LOG.write(line+"\n"); LOG.flush()
def handle(c,a):
    log(f"[8080] CONNESSO da {a[0]}:{a[1]} <-- cerca la wallbox!")
    c.settimeout(30)
    try:
        while True:
            d=c.recv(1024)
            if not d: break
            t=d.decode('ascii','replace').replace('\r',' ').replace('\n',' ').strip()
            log(f"[8080] <- hex={d.hex()} testo={t!r}")
    except Exception as e: log(f"[8080] {e}")
    finally: c.close(); log(f"[8080] chiuso {a[0]}")
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("0.0.0.0",8080)); s.listen(5); log("[8080] in ascolto")
while True:
    conn,addr=s.accept(); threading.Thread(target=handle,args=(conn,addr),daemon=True).start()
