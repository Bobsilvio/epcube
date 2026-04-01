from datetime import date

class EpCubeDataState:
    def __init__(self):
        self.last_battery_energy = None
        self.total_in = 0.0
        self.total_out = 0.0
        self.daily_in = 0.0
        self.daily_out = 0.0
        self.last_reset = date.today()

    def reset_daily(self):
        self.daily_in = 0.0
        self.daily_out = 0.0
        self.last_reset = date.today()

    # Soglia minima per ignorare oscillazioni di misura dell'API (risoluzione 0.01 kWh)
    MIN_DELTA_KWH = 0.05

    def update(self, battery_now: float):
        today = date.today()
        if today != self.last_reset:
            self.reset_daily()

        if self.last_battery_energy is None:
            self.last_battery_energy = battery_now
            return

        delta = battery_now - self.last_battery_energy

        if delta >= self.MIN_DELTA_KWH:
            self.total_in += delta
            self.daily_in += delta
            self.last_battery_energy = battery_now
        elif delta <= -self.MIN_DELTA_KWH:
            self.total_out += abs(delta)
            self.daily_out += abs(delta)
            self.last_battery_energy = battery_now
        # Se |delta| < MIN_DELTA_KWH, non aggiornare last_battery_energy:
        # il valore rimane "ancorato" finché la variazione non è reale

