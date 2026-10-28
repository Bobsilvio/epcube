# Ascoltatore Modbus TCP 502: il canale con cui il GATEWAY EP Cube cerca la wallbox.
# Risponde come un server Modbus valido (registri a zero) per far proseguire il dialogo.
import socket, threading, time
LOG=open("tools/wallbox_502.log","a")
def log(m):
    line=f"{time.strftime('%H:%M:%S')} {m}"; print(line,flush=True); LOG.write(line+"\n"); LOG.flush()
def reply(req):
    if len(req)<12: return None
    tid=req[0:2]; unit=req[6]; fn=req[7]
    if fn in (3,4):
        qty=int.from_bytes(req[10:12],'big'); p=bytes([unit,fn,qty*2])+b'\x00'*(qty*2)
    elif fn in (6,16): p=bytes([unit,fn])+req[8:12]
    else: p=bytes([unit,fn|0x80,1])
    return tid+b'\x00\x00'+len(p).to_bytes(2,'big')+p
def handle(c,a):
    log(f"[502] CONNESSO da {a[0]}:{a[1]}  <-- il GATEWAY cerca la wallbox!")
    c.settimeout(60)
    try:
        while True:
            d=c.recv(512)
            if not d: break
            log(f"[502] <- {d.hex()}")
            r=reply(d)
            if r: c.sendall(r); log(f"[502] -> {r.hex()}")
    except Exception as e: log(f"[502] {e}")
    finally: c.close(); log(f"[502] chiuso {a[0]}")
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("0.0.0.0",502)); s.listen(5); log("[502] in ascolto")
while True:
    c,a=s.accept(); threading.Thread(target=handle,args=(c,a),daemon=True).start()
