from datetime import date

class EpCubeDataState:
    def __init__(self):
        self.last_battery_energy = None
        self.total_in = 0.0
        self.total_out = 0.0
        self.daily_in = 0.0
        self.daily_out = 0.0
        self.last_reset = date.today()
        # Cache degli endpoint lenti (extras.py)
        self.extras = None
        self.extras_at = 0.0
        # Endpoint che il server della regione non espone (HTTP 404): non si
        # richiamano fino al prossimo reload dell'integrazione
        self.unsupported = set()
        # Serie a 5 minuti di oggi (queryDataGraphV2), vedi extras.py
        self.series = None
        self.series_at = 0.0
        # Contabilità dei totali dalla serie misurata: giorno e valori
        # giornalieri già sommati in total_in/total_out
        self.series_mode = False
        self.series_needs_baseline = True
        self.series_day = None
        self.series_seen_in = 0.0
        self.series_seen_out = 0.0

    def reset_daily(self):
        self.daily_in = 0.0
        self.daily_out = 0.0
        self.last_reset = date.today()

    # Soglia minima per ignorare oscillazioni di misura dell'API (risoluzione 0.01 kWh)
    MIN_DELTA_KWH = 0.05

    def update(self, battery_now: float):
        """Stima carica/scarica dalla variazione dell'energia accumulata.

        È il ripiego quando la serie misurata non è disponibile: una volta che
        la serie ha funzionato, i totali li aggiorna solo apply_series.
        """
        today = date.today()
        if today != self.last_reset:
            self.reset_daily()

        if self.last_battery_energy is None:
            self.last_battery_energy = battery_now
            return

        delta = battery_now - self.last_battery_energy

        if delta >= self.MIN_DELTA_KWH:
            self.daily_in += delta
            if not self.series_mode:
                self.total_in += delta
            self.last_battery_energy = battery_now
        elif delta <= -self.MIN_DELTA_KWH:
            self.daily_out += abs(delta)
            if not self.series_mode:
                self.total_out += abs(delta)
            self.last_battery_energy = battery_now
        # Se |delta| < MIN_DELTA_KWH, non aggiornare last_battery_energy:
        # il valore rimane "ancorato" finché la variazione non è reale

    def apply_series(self, day, charge, discharge, closing=None):
        """Porta nei totali la carica/scarica misurata del giorno.

        charge/discharge sono i kWh dalla mezzanotte di `day`; si somma solo la
        parte non ancora contata. closing = (giorno, carica, scarica) finali del
        giorno precedente, per non perdere l'ultimo tratto prima di mezzanotte.
        """
        if closing is not None and self.series_day == closing[0]:
            self._add(closing[1] - self.series_seen_in, closing[2] - self.series_seen_out)
            self.series_day = None

        if self.series_day == day:
            self._add(charge - self.series_seen_in, discharge - self.series_seen_out)
            self.series_seen_in = max(self.series_seen_in, charge)
            self.series_seen_out = max(self.series_seen_out, discharge)
        else:
            # Prima serie in assoluto: il giorno fin qui è già nei totali stimati
            if not self.series_needs_baseline:
                self._add(charge, discharge)
            self.series_day = day
            self.series_seen_in = charge
            self.series_seen_out = discharge

        self.series_needs_baseline = False
        self.series_mode = True

    def _add(self, energy_in, energy_out):
        # Il cloud può ritoccare al ribasso un punto: i totali non scendono mai
        if energy_in > 0:
            self.total_in += energy_in
        if energy_out > 0:
            self.total_out += energy_out
