[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

## Supportami

Se ti piace il mio lavoro e vuoi che continui nello sviluppo, puoi offrirmi un caffè.

[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)
[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)
[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)

# EP Cube per Home Assistant

🇬🇧 [English version](README.md)

Porta in Home Assistant il tuo accumulo EP Cube: batteria, fotovoltaico, rete e consumi. Puoi anche comandarlo come dall'app: cambiare modalità, riserve e fasce orarie, e forzare la batteria. Usa lo stesso cloud dell'app ufficiale.

---

## Installazione

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

1. In HACS aggiungi il repository personalizzato `https://github.com/Bobsilvio/epcube` (tipo *Integrazione*) e installa **EPCube**
2. Riavvia Home Assistant
3. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → EP Cube**
4. Scegli la regione del tuo account (EU, US o JP) e inserisci **email e password dell'app EP Cube**

Con email e password l'accesso si rinnova da solo.

Da **⋮ → Opzioni** puoi cambiare ogni quanti secondi leggere i dati (default 5) e attivare i contatori annuali, mensili e totali.

---

## Ogni quanto si aggiornano i valori

| Dati | Ogni quanto |
|---|---|
| Potenze (solare, rete, casa, batteria), SoC, presenza rete | ogni 5 secondi (o quanto impostato nelle opzioni) |
| Energia di oggi e di ieri (solare, prelievo, immissione, consumi) | ogni 5 secondi |
| Modalità, riserve, fasce orarie | ogni 5 secondi |
| **Carica e scarica della batteria** | **ogni 10 minuti** |
| Firmware, avvisi e guasti, blackout, meteo, Wi-Fi | ogni 15 minuti, oppure subito col pulsante **Controlla aggiornamenti** |

---

## Comandi

Tutto si comanda dalla pagina del dispositivo (**Impostazioni → Dispositivi e servizi → EP Cube**), sezione *Configurazione*, o da una card della dashboard. Non serve scrivere YAML.

| Entità | A cosa serve |
|---|---|
| **Modalità** | Autoconsumo, Tariffazione, Backup (e Tariffa dinamica se il tuo impianto la prevede) |
| **Riserva SOC autoconsumo** | In Autoconsumo la batteria non scende sotto questo livello |
| **Riserva SOC back-up** | In Backup la batteria tiene da parte questa carica per i blackout |
| **Consentire la ricarica tramite rete** | Permette alla batteria di caricarsi dalla rete (in Tariffazione e Backup) |
| **Orari costo alto / normale / basso** e **Prezzo costo …** | Le fasce orarie della Tariffazione, [vedi sotto](#tariffazione-fasce-orarie) |
| **Override batteria** | Forza carica, Forza scarica o Mantieni per un certo tempo, [vedi sotto](#override-batteria) |
| **Controlla aggiornamenti** | Rilegge subito firmware, avvisi e blackout |

Cambiare un valore non tocca gli altri.

Su alcuni impianti la ricarica da rete è bloccata dall'installatore: in quel caso l'interruttore dà errore invece di far finta di funzionare.

### Tariffazione (fasce orarie)

Serve a usare la batteria in base al costo dell'energia: in generale si carica quando l'energia costa poco e si usa quando costa tanto.

**Come si imposta:**

1. Per ogni tipo di fascia (costo alto, normale, basso) scrivi gli orari in **Orari costo …**, separati da una virgola:

   ```
   08:00-13:00, 20:00-23:00
   ```

   Al massimo 3 fasce per tipo. Se il formato è sbagliato Home Assistant non accetta il testo. Per togliere tutte le fasce di un tipo, svuota la casella.
2. Se vuoi, metti il prezzo in **Prezzo costo …** (vale per tutte le fasce di quel tipo).
3. Scegli **Modalità → Tariffazione**.

Salvare orari e prezzi non cambia modalità: puoi prepararli prima e attivarli quando vuoi.

Esempio con le fasce italiane F1/F2/F3 nei giorni feriali:

| Tipo | Orari |
|---|---|
| Costo alto (F1) | `08:00-19:00` |
| Costo normale (F2) | `07:00-08:00, 19:00-23:00` |
| Costo basso (F3) | `00:00-07:00, 23:00-24:00` |

Orari e prezzi valgono per i giorni feriali (lunedì-venerdì). Le fasce del fine settimana e dell'ora legale si impostano dall'app o con l'azione `epcube.set_tou_schedule` ([esempi](ESEMPI_TOU_SERVICE.md)).

Se il tuo EP Cube ha il firmware con i piani stagionali (4.0.8 o successivo), queste entità risultano non disponibili: in quel caso la Tariffazione si imposta solo dall'app.

### Override batteria

Serve a forzare la batteria per un po' di tempo, per esempio per tenerla carica prima di un temporale.

1. Imposta **SoC obiettivo override** (il livello) e **Durata override** (in minuti; 0 = finché non lo annulli)
2. Scegli cosa fare in **Override batteria**:

| Scelta | Cosa succede |
|---|---|
| **Forza carica** | La batteria smette di scaricarsi e si ricarica col solare fino al SoC obiettivo. Non carica dalla rete |
| **Forza scarica** | La batteria può alimentare la casa fino al SoC obiettivo |
| **Mantieni** | La batteria resta al livello attuale |
| **Nessuno** | Annulla subito |

Funziona solo in modalità **Autoconsumo**. Alla fine la riserva di prima torna da sola, anche se nel frattempo Home Assistant viene riavviato.

---

## Dashboard Energia

In **Impostazioni → Dashboard → Energia**:

| Voce | Sensore |
|---|---|
| Produzione solare | **Energia Fotovoltaico Giornaliera** |
| Consumo dalla rete | **Energia Prelevata da Rete** |
| Immissione in rete | **Energia Immessa in Rete** |
| Energia nella batteria | **Totale Energia Accumulata** |
| Energia dalla batteria | **Totale Energia Erogata** |

---

## Automazioni

I comandi sopra si usano nelle automazioni come qualsiasi entità (`select.select_option`, `number.set_value`, `text.set_value`). In più ci sono azioni dedicate:

| Azione | A cosa serve |
|---|---|
| `epcube.force_charge`, `epcube.force_discharge`, `epcube.hold_battery`, `epcube.clear_battery_override` | Override batteria con SoC e durata scritti nell'automazione |
| `epcube.set_operating_mode` | Cambia modalità e riserva in un colpo solo |
| `epcube.set_tou_schedule` | Imposta tutte le fasce, anche fine settimana e ora legale ([esempi](ESEMPI_TOU_SERVICE.md)) |

```yaml
# Alle 18 tieni la batteria carica per 2 ore
triggers:
  - trigger: time
    at: "18:00:00"
actions:
  - action: epcube.hold_battery
    data:
      duration: 120
```

```yaml
# Accorgersi di un blackout
triggers:
  - trigger: state
    entity_id: binary_sensor.epcube_off_grid
    to: "on"
```

Dal cloud un blackout e il magnetotermico scattato tra rete ed EP Cube sono indistinguibili.

---

## Sensori

- **Batteria**: SoC, potenza, stato (in carica / in scarica / ferma), carica e scarica di oggi e totali
- **Fotovoltaico**: potenza ed energia, per ogni stringa anche tensione e corrente
- **Rete**: potenza, energia prelevata e immessa, presenza rete, blackout
- **Casa**: consumo totale, carichi di backup e non di backup
- **Ieri**: energia prodotta, prelevata, immessa e consumata
- **Diagnostica**: firmware, Wi-Fi, ultimo avviso e guasto, ultimo blackout, meteo

<details>
<summary>Cosa significano i codici numerici</summary>

| Campo | Valore | Significato |
|---|---|---|
| Modalità operativa (`workStatus`) | 1 / 2 / 3 | Autoconsumo / Tariffazione / Backup |
| | 6 | Programma del gestore, non modificabile |
| Stato di funzionamento (`systemStatus`) | 2 | Inattivo (un minuto al risveglio) |
| | 4 | In funzione |
| | 6 | Bassa potenza: di notte, batteria al minimo |
| | 1 / 7 | Guasto / In protezione |
| `status` | 0 / 1 | Blackout / Collegato alla rete |
| `isOnline` | 0 / 1 | Gateway scollegato / collegato al cloud |
| `isAlert`, `isFault` | 0 / 1 | Niente / Avviso o guasto presente |
| `gridLight` | 0 / 1 | Rete assente / presente |
| `backupLoadsMode` | 0 / 1 | Backup parziale / Backup intera casa |
| `networking` | 1 / 3 | Wi-Fi / 4G |
| Modalità invernale (`winterProtect`) | 85 / 170 | Spenta / Accesa |
| Blackout Rete (`gridPowerFailureNum`) | contatore | Aumenta di uno quando la rete torna |

</details>

---

## Se qualcosa non va

- **"Token scaduto" appena configurato**: quasi sempre è la regione sbagliata. Un account esiste solo su EU, US o JP.
- **Un comando dà errore**: leggi il messaggio, di solito spiega il motivo (modalità sbagliata, funzione bloccata dall'installatore).
- **Per una segnalazione**: **Impostazioni → Dispositivi e servizi → EP Cube → ⋮ → Scarica diagnostica** e allegala. Credenziali, numeri di serie e posizione vengono oscurati.

---

## Disclaimer

Progetto non affiliato né approvato da EP Cube o Canadian Solar. L'API non è documentata né supportata ufficialmente: usalo a tuo rischio.
