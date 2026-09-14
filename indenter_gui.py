"""
Automated Muscle Indenter System - Graphical User Interface
Replaces:
- S1_parametetsSetting2017.vi (Control Front Panel)
- S2_Motor_Set speed2015.vi (Serial Motor Setup)
- S3Acq_fource_ai0.vi (DAQ Live Display)
- S3Motor_control2017m.vi (Motion Sequencer)
- S4_Youngs_Graph.vi (Real-Time XY Graph & Young's Modulus)
"""

import sys
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config import IndenterConfig
from indenter_pipeline import IndenterPipeline


class IndenterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Automated Muscle Indenter System (Taiwan AU Project)")
        self.geometry("1280x820")
        self.minsize(1050, 720)

        self.config = IndenterConfig()
        self.pipeline: IndenterPipeline | None = None
        self.is_sim_mode = tk.BooleanVar(value=True)

        self._setup_styles()
        self._build_ui()
        self._init_pipeline()

        # Timer for polling UI updates safely on Tkinter thread
        self.after(100, self._poll_gui_refresh)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=5)
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Card.TFrame", relief="groove", padding=10)

    def _build_ui(self):
        # Main split container: Left panel (Settings & Control), Right panel (Graphs)
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ================= LEFT CONTROL PANEL =================
        left_frame = ttk.Frame(main_paned, width=380)
        main_paned.add(left_frame, weight=0)

        # Title
        title_lbl = ttk.Label(
            left_frame,
            text="UT Muscle Indenter Controller\n(楊氏係數量測系統)",
            font=("Segoe UI", 13, "bold"),
            justify=tk.CENTER
        )
        title_lbl.pack(fill=tk.X, pady=(0, 10))

        # --- Card 1: Hardware & Connection ---
        hw_card = ttk.LabelFrame(left_frame, text="Hardware & Ports", padding=8)
        hw_card.pack(fill=tk.X, pady=5)

        ttk.Label(hw_card, text="Motor Port (COM):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.entry_port = ttk.Entry(hw_card, width=12)
        self.entry_port.insert(0, self.config.serial_port)
        self.entry_port.grid(row=0, column=1, sticky=tk.E, pady=2)

        ttk.Label(hw_card, text="DAQ Channel:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_daq = ttk.Entry(hw_card, width=12)
        self.entry_daq.insert(0, self.config.daq_channel)
        self.entry_daq.grid(row=1, column=1, sticky=tk.E, pady=2)

        ttk.Label(hw_card, text="Cal. Factor (N/V):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_cal = ttk.Entry(hw_card, width=12)
        self.entry_cal.insert(0, str(self.config.force_calibration_factor))
        self.entry_cal.grid(row=2, column=1, sticky=tk.E, pady=2)

        chk_sim = ttk.Checkbutton(hw_card, text="Simulation Mode (Offline)", variable=self.is_sim_mode, command=self._on_sim_toggle)
        chk_sim.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=4)

        btn_tare = ttk.Button(hw_card, text="Tare Sensor (Zero N)", command=self._on_tare)
        btn_tare.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)

        # --- Card 2: Indentation Parameters (S1 parameters) ---
        param_card = ttk.LabelFrame(left_frame, text="Indenter Protocol (S1 設定)", padding=8)
        param_card.pack(fill=tk.X, pady=5)

        ttk.Label(param_card, text="Target Depth (mm) / 前進距離:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.entry_depth = ttk.Entry(param_card, width=10)
        self.entry_depth.insert(0, str(self.config.target_displacement_mm))
        self.entry_depth.grid(row=0, column=1, sticky=tk.E, pady=2)

        ttk.Label(param_card, text="Repeat Cycles / 重複次數:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_cycles = ttk.Entry(param_card, width=10)
        self.entry_cycles.insert(0, str(self.config.repeat_cycles))
        self.entry_cycles.grid(row=1, column=1, sticky=tk.E, pady=2)

        ttk.Label(param_card, text="Dwell Time (s) / 停留時間:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_dwell = ttk.Entry(param_card, width=10)
        self.entry_dwell.insert(0, str(self.config.dwell_time_s))
        self.entry_dwell.grid(row=2, column=1, sticky=tk.E, pady=2)

        ttk.Label(param_card, text="Retract Time (s) / 上升時間:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.entry_retract = ttk.Entry(param_card, width=10)
        self.entry_retract.insert(0, str(self.config.retract_time_s))
        self.entry_retract.grid(row=3, column=1, sticky=tk.E, pady=2)

        ttk.Label(param_card, text="Motor Top Speed / 速度參數:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.entry_speed = ttk.Entry(param_card, width=10)
        self.entry_speed.insert(0, str(self.config.top_speed))
        self.entry_speed.grid(row=4, column=1, sticky=tk.E, pady=2)

        # --- Card 3: Live Readouts & Modulus Results ---
        res_card = ttk.LabelFrame(left_frame, text="Live Readings & Modulus", padding=8)
        res_card.pack(fill=tk.X, pady=5)

        self.lbl_force = ttk.Label(res_card, text="Force: 0.000 N (0.000 V)", font=("Segoe UI", 11, "bold"))
        self.lbl_force.pack(anchor=tk.W, pady=2)

        self.lbl_pos = ttk.Label(res_card, text="Displacement: 0.00 mm (0 steps)", font=("Segoe UI", 10))
        self.lbl_pos.pack(anchor=tk.W, pady=2)

        self.lbl_status = ttk.Label(res_card, text="Status: IDLE", foreground="gray", font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(anchor=tk.W, pady=2)

        ttk.Separator(res_card, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # Young's Modulus Table
        mod_frame = ttk.Frame(res_card)
        mod_frame.pack(fill=tk.X)
        self.lbl_e1 = ttk.Label(mod_frame, text="E1: --- kPa", font=("Segoe UI", 10, "bold"), foreground="#0066cc")
        self.lbl_e1.grid(row=0, column=0, sticky=tk.W, padx=4)
        self.lbl_e2 = ttk.Label(mod_frame, text="E2: --- kPa", font=("Segoe UI", 10, "bold"), foreground="#0066cc")
        self.lbl_e2.grid(row=0, column=1, sticky=tk.W, padx=4)
        self.lbl_e3 = ttk.Label(mod_frame, text="E3: --- kPa", font=("Segoe UI", 10, "bold"), foreground="#0066cc")
        self.lbl_e3.grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.lbl_emean = ttk.Label(mod_frame, text="E_mean: --- kPa", font=("Segoe UI", 10, "bold"), foreground="#cc0000")
        self.lbl_emean.grid(row=1, column=1, sticky=tk.W, padx=4, pady=2)

        # --- Card 4: Action Buttons ---
        act_card = ttk.Frame(left_frame)
        act_card.pack(fill=tk.X, pady=10)

        self.btn_start = tk.Button(
            act_card, text="▶ START TEST (啟動)", bg="#28a745", fg="white",
            font=("Segoe UI", 11, "bold"), height=2, command=self._on_start
        )
        self.btn_start.pack(fill=tk.X, pady=3)

        self.btn_stop = tk.Button(
            act_card, text="⏹ STOP / ABORT", bg="#dc3545", fg="white",
            font=("Segoe UI", 10, "bold"), command=self._on_stop, state=tk.DISABLED
        )
        self.btn_stop.pack(fill=tk.X, pady=3)

        btn_export = ttk.Button(act_card, text="💾 Export Data (LabVIEW Format)", command=self._on_export)
        btn_export.pack(fill=tk.X, pady=3)

        # ================= RIGHT GRAPHING PANEL =================
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Build Matplotlib Figures (2 subplots: F-d Hysteresis & F-t Profile)
        self.fig = Figure(figsize=(7, 7), dpi=100)
        self.ax_fd = self.fig.add_subplot(2, 1, 1)
        self.ax_ft = self.fig.add_subplot(2, 1, 2)
        self.fig.tight_layout(pad=3.0)

        self._init_plots()

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _init_plots(self):
        # Top: Force vs Displacement (S4_Youngs_Graph Chart of Fource & Dislpacement)
        self.ax_fd.clear()
        self.ax_fd.set_title("Force vs. Displacement (Hysteresis Loop)", fontsize=11, fontweight="bold")
        self.ax_fd.set_xlabel("Displacement w (mm)")
        self.ax_fd.set_ylabel("Force P (N)")
        self.ax_fd.grid(True, linestyle="--", alpha=0.6)
        self.line_fd, = self.ax_fd.plot([], [], "b-", lw=1.8, label="Indentation")
        self.ax_fd.legend(loc="upper left")

        # Bottom: Force & Displacement vs Time
        self.ax_ft.clear()
        self.ax_ft.set_title("Force & Displacement vs. Time (Siklus Pembebanan)", fontsize=11, fontweight="bold")
        self.ax_ft.set_xlabel("Time (s)")
        self.ax_ft.set_ylabel("Force (N)", color="tab:red")
        self.ax_ft.tick_params(axis="y", labelcolor="tab:red")
        self.ax_ft.grid(True, linestyle="--", alpha=0.6)
        self.line_ft, = self.ax_ft.plot([], [], "r-", lw=1.5, label="Force (N)")

        # Secondary y-axis for displacement
        if not hasattr(self, "ax_dt"):
            self.ax_dt = self.ax_ft.twinx()
        else:
            self.ax_dt.clear()
        self.ax_dt.set_ylabel("Displacement (mm)", color="tab:blue")
        self.ax_dt.tick_params(axis="y", labelcolor="tab:blue")
        self.line_dt, = self.ax_dt.plot([], [], "b--", lw=1.2, label="Disp (mm)")

    def _init_pipeline(self):
        self._apply_inputs_to_config()
        self.pipeline = IndenterPipeline(self.config, simulation_mode=self.is_sim_mode.get())
        self.pipeline.on_cycle_complete = self._on_cycle_done
        self.pipeline.on_experiment_finish = self._on_exp_finish
        self.pipeline.initialize()

    def _apply_inputs_to_config(self):
        try:
            self.config.serial_port = self.entry_port.get().strip()
            self.config.daq_channel = self.entry_daq.get().strip()
            self.config.force_calibration_factor = float(self.entry_cal.get())
            self.config.target_displacement_mm = float(self.entry_depth.get())
            self.config.repeat_cycles = int(self.entry_cycles.get())
            self.config.dwell_time_s = float(self.entry_dwell.get())
            self.config.retract_time_s = float(self.entry_retract.get())
            self.config.top_speed = int(self.entry_speed.get())
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numeric parameters: {e}")

    def _on_sim_toggle(self):
        if self.pipeline:
            self.pipeline.shutdown()
        self._init_pipeline()

    def _on_tare(self):
        if self.pipeline:
            tare_v = self.pipeline.daq.tare()
            messagebox.showinfo("Tare Complete", f"Load cell zeroed. Baseline offset: {tare_v:.4f} V")

    def _on_start(self):
        self._apply_inputs_to_config()
        self._init_plots()
        self.canvas.draw()

        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.lbl_status.config(text="Status: RUNNING (啟動中)", foreground="green")

        self.pipeline.run_experiment_async()

    def _on_stop(self):
        if self.pipeline:
            self.pipeline.is_running = False
        self.lbl_status.config(text="Status: STOPPED", foreground="red")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def _on_cycle_done(self, cycle: int, results: dict):
        self.after(0, lambda: self._update_modulus_labels(results))

    def _on_exp_finish(self, overall_results: dict):
        self.after(0, lambda: self._handle_finish(overall_results))

    def _handle_finish(self, overall_results: dict):
        self.lbl_status.config(text="Status: COMPLETED", foreground="blue")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self._update_modulus_labels(overall_results)
        messagebox.showinfo(
            "Indentation Test Finished",
            f"Measurement complete!\n"
            f"E1: {overall_results.get('E1_kPa', 0.0)} kPa\n"
            f"E2: {overall_results.get('E2_kPa', 0.0)} kPa\n"
            f"E3: {overall_results.get('E3_kPa', 0.0)} kPa\n"
            f"Mean Modulus: {overall_results.get('E_mean_kPa', 0.0)} kPa"
        )

    def _update_modulus_labels(self, results: dict):
        self.lbl_e1.config(text=f"E1: {results.get('E1_kPa', '---')} kPa")
        self.lbl_e2.config(text=f"E2: {results.get('E2_kPa', '---')} kPa")
        self.lbl_e3.config(text=f"E3: {results.get('E3_kPa', '---')} kPa")
        self.lbl_emean.config(text=f"E_mean: {results.get('E_mean_kPa', '---')} kPa")

    def _on_export(self):
        if not self.pipeline or not self.pipeline.data_records:
            messagebox.showwarning("No Data", "No indentation data available to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Tab Delimited File (*.txt)", "*.txt"), ("CSV File (*.csv)", "*.csv")],
            initialfile="NOAH_INDENTER_DATA.txt"
        )
        if path:
            self.pipeline.export_data(path)
            messagebox.showinfo("Export Successful", f"Saved {len(self.pipeline.data_records)} data rows to:\n{path}")

    def _poll_gui_refresh(self):
        """Periodic refresh for labels and live plots."""
        if self.pipeline:
            # Read latest sensor values
            raw_v, force_n = self.pipeline.daq.read_sample()
            pos_steps = self.pipeline.motor.current_step_pos
            disp_mm = self.pipeline.motor.get_displacement_mm()

            self.lbl_force.config(text=f"Force: {force_n:.3f} N ({raw_v:.3f} V)")
            self.lbl_pos.config(text=f"Displacement: {disp_mm:.2f} mm ({pos_steps} steps)")

            # Update plots if experiment is active and new data exists
            records = self.pipeline.data_records
            if records and self.pipeline.is_running:
                disps = [r["disp_mm"] for r in records]
                forces = [r["force_n"] for r in records]
                times = [r["timestamp_ms"] / 1000.0 for r in records]

                # Update F-d curve
                self.line_fd.set_data(disps, forces)
                self.ax_fd.relim()
                self.ax_fd.autoscale_view()

                # Update F-t and d-t profiles
                self.line_ft.set_data(times, forces)
                self.line_dt.set_data(times, disps)
                self.ax_ft.relim()
                self.ax_ft.autoscale_view()
                self.ax_dt.relim()
                self.ax_dt.autoscale_view()

                self.canvas.draw_idle()

        self.after(100, self._poll_gui_refresh)


if __name__ == "__main__":
    app = IndenterApp()
    app.mainloop()
