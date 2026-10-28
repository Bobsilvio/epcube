# Richiesta a EP Cube: firmware V1.3.0 e funzione Caricatore EV

Due richieste in un solo messaggio:

1. **pubblicare la V1.3.0** sul gateway (risulta già assegnata, ma l'app non la propone);
2. **abilitare il Caricatore EV** sull'account (`kebaAuthority`), e già che ci siamo Home Connect.

Sotto, lo stesso testo in inglese e in italiano. Contatti: `support@epcube.com`,
il modulo Assistenza dentro l'app, oppure l'installatore.

Dati da inserire al posto dei segnaposto:

| Campo | Valore |
|---|---|
| Numero di serie (SG SN) | `100100004001245250049` |
| Seriale RTU | `VD06000324208235` |
| Account | `<email dell'account EP Cube>` |
| Impianto | monofase (1Phase) |
| Firmware installato | V1.3.0 (RTU V1.0.0.4) |
| App | EP Cube EU 3.1.1 (iOS) |

---

## Versione inglese

**Subject: Firmware V1.3.0 and EV Charger activation — SN 100100004001245250049**

Hello,

I own an EP Cube single-phase system (SN `100100004001245250049`, RTU
`VD06000324208235`, account `<email>`), currently on firmware **V1.3.0**
(RTU V1.0.0.4). I have two requests.

**1. Please push firmware V1.3.0 to my gateway.**
I understand V1.3.0 is the current release. My gateway still reports V1.2.2 and
the app's update page says "this is already the latest version", so I cannot
start the update myself even though automatic updates are enabled.

**2. Please enable the EV Charger feature on my account.**
Settings → Partnership shows "Feature not available". As far as I can tell the
EV Charger entry depends on the account flag `kebaAuthority`, which is `0` on my
account. Could you set it to `1`? If possible, please also enable the Home
Connect permission.

**One technical question, so the two requests are not independent.**
With the current firmware, the registers that configure the wallbox are accepted
by the cloud but appear not to be stored by the gateway:

- writing the "Modbus TCP server enable" and "auto scan enable" registers
  (`0x1446`, `0x1447`) returns Success, but reading them back a few seconds later
  returns `0`;
- the same happens with the manual wallbox IP (`0x1448`/`0x1449`);
- the scan result registers (`0x141C` auto, `0x141D` manual) always stay at `0`
  (idle) and never change, not even after the full manual timeout;
- reading an unrelated register (battery SoC) over the same API works correctly,
  so the read path itself is fine.

Does **V1.3.0 implement the wallbox function for single-phase units**? If it does
not, could you tell me which firmware version does?

Thank you very much.

Best regards,
`<nome>`

---

## Versione italiana

**Oggetto: firmware V1.3.0 e attivazione Caricatore EV — SN 100100004001245250049**

Buongiorno,

ho un sistema EP Cube monofase (SN `100100004001245250049`, RTU
`VD06000324208235`, account `<email>`), attualmente con firmware **V1.3.0**
(RTU V1.0.0.4). Avrei due richieste.

**1. Vi chiedo di pubblicare il firmware V1.3.0 sul mio gateway.**
Mi risulta che la V1.3.0 sia la versione attuale. Il mio gateway riporta ancora
la V1.2.2 e la pagina di aggiornamento dell'app dice "Questa è già l'ultima
versione", quindi non posso avviare io l'aggiornamento, pur avendo
l'aggiornamento automatico attivo.

**2. Vi chiedo di abilitare la funzione Caricatore EV sul mio account.**
In Impostazioni → Partenariato compare "Funzione non disponibile". Da quanto ho
capito la voce Caricatore EV dipende dal permesso `kebaAuthority` dell'account,
che sul mio risulta `0`. Potete impostarlo a `1`? Se possibile, abilitate anche
il permesso Home Connect.

**Una domanda tecnica, perché le due richieste sono collegate.**
Con il firmware attuale, i registri che configurano la wallbox vengono accettati
dal cloud ma sembrano non essere memorizzati dal gateway:

- la scrittura dei registri "abilita server Modbus TCP" e "abilita ricerca
  automatica" (`0x1446`, `0x1447`) risponde Success, ma rileggendoli pochi
  secondi dopo il valore è `0`;
- lo stesso accade con l'IP manuale della wallbox (`0x1448`/`0x1449`);
- i registri con l'esito della ricerca (`0x141C` automatica, `0x141D` manuale)
  restano sempre a `0` (inattivo) e non cambiano mai, nemmeno dopo il timeout
  completo della ricerca manuale;
- la lettura di un registro non collegato (SoC della batteria) tramite la stessa
  API funziona correttamente, quindi la lettura di per sé è a posto.

La **V1.3.0 implementa la funzione wallbox per le unità monofase**? In caso
contrario, potete indicarmi quale versione la supporta?

Grazie mille.

Cordiali saluti,
`<nome>`

---

## Dopo l'aggiornamento

Quando il gateway è passato alla V1.3.0, verifica subito se la funzione c'è
davvero, senza aspettare che l'app mostri qualcosa:

- da Home Assistant: **Strumenti per sviluppatori → Azioni → EP CUBE: Verifica
  supporto wallbox**;
- oppure da terminale: `python3 tools/verifica_wallbox.py`.

Se il registro `1446` resta a **1** dopo la scrittura, il firmware supporta la
wallbox: a quel punto entra in gioco l'integrazione `epcube_wallboxbridge`, e
nell'app basta indicare l'IP di Home Assistant come indirizzo della wallbox.

Se resta a **0**, nemmeno la V1.3.0 include la funzione, e va chiesto a EP Cube
quale firmware la supporti.
