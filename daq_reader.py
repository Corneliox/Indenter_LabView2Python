"""
DAQ Reader Module (Replacing S3Acq_fource_ai0.vi)
Reads analog voltage from NI-DAQmx, calibrates tare offset,
and converts voltage to force in Newtons (N).
Includes automatic hardware simulation fallback.
"""

import time
import threading
from typing import Optional, Callable
from config import IndenterConfig

# Try importing NI-DAQmx library
try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration
    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False


class DaqReader:
    def __init__(self, config: IndenterConfig, simulation_mode: bool = False):
        self.config = config
        self.simulation_mode = simulation_mode or (not NIDAQMX_AVAILABLE)
        
        self.tare_voltage: float = self.config.tare_voltage_offset
        self.latest_raw_voltage: float = 0.0
        self.latest_force_newton: float = 0.0
        
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # External hook to query simulated displacement if in simulation mode
        self.simulated_displacement_fn: Optional[Callable[[], float]] = None

    def start(self):
        """Start background sampling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop background sampling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def tare(self, num_samples: int = 20):
        """Zero the load cell sensor by setting the current average voltage as baseline."""
        voltages = []
        for _ in range(num_samples):
            v, _ = self.read_sample()
            voltages.append(v)
            time.sleep(0.01)
        if voltages:
            with self._lock:
                self.tare_voltage = sum(voltages) / len(voltages)
        return self.tare_voltage

    def read_sample(self) -> tuple[float, float]:
        """
        Returns (raw_voltage, force_newton).
        Thread-safe single read.
        """
        with self._lock:
            return self.latest_raw_voltage, self.latest_force_newton

    def _convert_voltage_to_newton(self, raw_v: float) -> float:
        """
        Converts load cell amplifier voltage to Newtons.
        F (N) = (V - V_tare) * K_cal
        """
        delta_v = max(0.0, raw_v - self.tare_voltage)
        return delta_v * self.config.force_calibration_factor

    def _sampling_loop(self):
        """Continuous background acquisition loop."""
        interval = 1.0 / self.config.daq_sample_rate

        if not self.simulation_mode:
            try:
                with nidaqmx.Task() as task:
                    task.ai_channels.add_ai_voltage_chan(
                        self.config.daq_channel,
                        min_val=self.config.voltage_min,
                        max_val=self.config.voltage_max,
                        terminal_config=TerminalConfiguration.DEFAULT
                    )
                    while self._running:
                        t_start = time.perf_counter()
                        # Read 1 sample from analog channel
                        raw_v = float(task.read())
                        force_n = self._convert_voltage_to_newton(raw_v)

                        with self._lock:
                            self.latest_raw_voltage = raw_v
                            self.latest_force_newton = force_n

                        elapsed = time.perf_counter() - t_start
                        sleep_time = max(0.0, interval - elapsed)
                        time.sleep(sleep_time)
                return
            except Exception as e:
                print(f"[DAQ Warning] Real DAQmx error ({e}). Switching to simulation mode.")
                self.simulation_mode = True

        # Fallback / Simulation Mode
        while self._running:
            t_start = time.perf_counter()
            
            # If a motor displacement function is hooked, compute realistic tissue force
            current_disp = 0.0
            if self.simulated_displacement_fn:
                current_disp = self.simulated_displacement_fn()
                
            # Non-linear viscoelastic tissue response: F = k1 * d + k2 * d^2
            simulated_force = max(0.0, 1.8 * current_disp + 0.8 * (current_disp ** 2))
            sim_v = self.tare_voltage + (simulated_force / self.config.force_calibration_factor)

            with self._lock:
                self.latest_raw_voltage = sim_v
                self.latest_force_newton = simulated_force

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.0, interval - elapsed)
            time.sleep(sleep_time)
