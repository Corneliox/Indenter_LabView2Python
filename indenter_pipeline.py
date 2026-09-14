"""
Indenter Pipeline & Experiment Sequencer
Replaces S3Motor_control2017m.vi and links DAQ acquisition,
motor cyclic execution, live logging, and Young's Modulus calculation.
"""

import time
import threading
from typing import Callable, Optional
import numpy as np
import pandas as pd

from config import IndenterConfig
from daq_reader import DaqReader
from motor_controller import MotorController
from youngs_modulus import calculate_effective_youngs_modulus


class IndenterPipeline:
    def __init__(self, config: IndenterConfig, simulation_mode: bool = False):
        self.config = config
        self.simulation_mode = simulation_mode
        
        self.daq = DaqReader(config, simulation_mode=simulation_mode)
        self.motor = MotorController(config, simulation_mode=simulation_mode)
        
        # Link simulated displacement to DAQ so synthetic data reflects real physics
        self.daq.simulated_displacement_fn = self.motor.get_displacement_mm
        
        self.is_running: bool = False
        self.current_cycle: int = 0
        self.data_records: list[dict] = []
        
        # Callbacks for GUI
        self.on_data_point: Optional[Callable[[dict], None]] = None
        self.on_cycle_complete: Optional[Callable[[int, dict], None]] = None
        self.on_experiment_finish: Optional[Callable[[dict], None]] = None

    def initialize(self) -> bool:
        """Connect motor and start DAQ sampling."""
        motor_ok = self.motor.connect()
        self.daq.start()
        # Perform initial tare
        time.sleep(0.2)
        self.daq.tare()
        return motor_ok

    def shutdown(self):
        """Safely halt motor and DAQ."""
        self.is_running = False
        self.motor.move_absolute(0)
        self.daq.stop()
        self.motor.disconnect()

    def run_experiment_async(self):
        """Launches experiment sequencer on a separate worker thread."""
        if self.is_running:
            return
        worker = threading.Thread(target=self._experiment_sequence, daemon=True)
        worker.start()

    def _experiment_sequence(self):
        """
        Executes cyclic indentation protocol:
        Matching S1 (重複次數, 前進距離, 速度, 停留時間) and S3Motor_control2017m.vi
        """
        self.is_running = True
        self.data_records.clear()
        
        # Target step count = distance_mm * steps_per_mm
        target_steps = int(self.config.target_displacement_mm * self.config.steps_per_mm)
        start_time = time.perf_counter()

        print(f"[Indenter] Starting {self.config.repeat_cycles} cycles | "
              f"Target: {self.config.target_displacement_mm} mm ({target_steps} steps)")

        # Configure motor speed
        self.motor.set_speed(
            self.config.start_speed,
            self.config.top_speed,
            self.config.accel_rate
        )

        for cycle in range(1, self.config.repeat_cycles + 1):
            if not self.is_running:
                break
            self.current_cycle = cycle
            print(f"[Indenter] Cycle {cycle}/{self.config.repeat_cycles}...")

            # --- 1. Forward Indentation (Loading Phase, ~3.0s) ---
            self.motor.move_relative(target_steps)
            self._sample_motion_phase(duration_s=3.0, start_time=start_time, cycle=cycle)

            # --- 2. Dwell Time (Hold at peak indentation) ---
            if self.config.dwell_time_s > 0 and self.is_running:
                self._sample_motion_phase(duration_s=self.config.dwell_time_s, start_time=start_time, cycle=cycle)

            # --- 3. Retraction (Unloading Phase, ~1.8s) ---
            if self.is_running:
                self.motor.move_absolute(0)
                self._sample_motion_phase(duration_s=self.config.retract_time_s, start_time=start_time, cycle=cycle)

            # Calculate Young's Modulus for this completed cycle
            cycle_df = pd.DataFrame([r for r in self.data_records if r["cycle"] == cycle])
            cycle_results = {}
            if not cycle_df.empty:
                cycle_results = calculate_effective_youngs_modulus(
                    force_n=cycle_df["force_n"].to_numpy(),
                    displacement_mm=cycle_df["disp_mm"].to_numpy(),
                    indenter_radius_mm=self.config.indenter_radius_mm,
                    tissue_thickness_mm=self.config.tissue_thickness_mm,
                    poisson_ratio=self.config.poisson_ratio
                )

            if self.on_cycle_complete:
                self.on_cycle_complete(cycle, cycle_results)

            # --- 4. Inter-cycle Rest Interval ---
            if cycle < self.config.repeat_cycles and self.is_running:
                time.sleep(self.config.cycle_rest_s)

        # Final return home
        self.motor.move_absolute(0)
        self.is_running = False

        # Overall analysis across all cycles
        df = pd.DataFrame(self.data_records)
        overall_results = {}
        if not df.empty:
            overall_results = calculate_effective_youngs_modulus(
                force_n=df["force_n"].to_numpy(),
                displacement_mm=df["disp_mm"].to_numpy(),
                indenter_radius_mm=self.config.indenter_radius_mm,
                tissue_thickness_mm=self.config.tissue_thickness_mm,
                poisson_ratio=self.config.poisson_ratio
            )

        print("[Indenter] Experiment completed successfully.")
        if self.on_experiment_finish:
            self.on_experiment_finish(overall_results)

    def _sample_motion_phase(self, duration_s: float, start_time: float, cycle: int):
        """Samples data synchronously at fixed intervals during a motion phase."""
        t_phase_start = time.perf_counter()
        sample_interval = 1.0 / self.config.daq_sample_rate

        while (time.perf_counter() - t_phase_start) < duration_s and self.is_running:
            t_loop = time.perf_counter()
            elapsed_ms = (t_loop - start_time) * 1000.0

            raw_v, force_n = self.daq.read_sample()
            pos_steps = self.motor.query_position()
            disp_mm = self.motor.get_displacement_mm()

            record = {
                "timestamp_ms": round(elapsed_ms, 2),
                "step_pos": pos_steps,
                "disp_mm": round(disp_mm, 4),
                "raw_voltage_v": round(raw_v, 4),
                "force_n": round(force_n, 4),
                "cycle": cycle
            }
            self.data_records.append(record)

            if self.on_data_point:
                self.on_data_point(record)

            dt = time.perf_counter() - t_loop
            sleep_t = max(0.0, sample_interval - dt)
            time.sleep(sleep_t)

    def export_data(self, filepath: str, format_type: str = "tsv"):
        """
        Exports collected data.
        'tsv' format reproduces LabVIEW Write To Spreadsheet File format:
        iSTEP \t Fource_LoadCell (V) \t Force (N) \t Timestamp (ms)
        """
        df = pd.DataFrame(self.data_records)
        if df.empty:
            print("[Warning] No data to export.")
            return

        if format_type.lower() == "tsv" or filepath.endswith(".txt"):
            # Format matching NOAH8010BEFORETA1 and S4_Youngs_Graph
            df.to_csv(filepath, sep="\t", index=False, float_format="%.3f")
        else:
            df.to_csv(filepath, index=False)
        print(f"[Indenter] Data exported to: {filepath}")
