"""
Configuration and Parameters for Automated Indenter System
Reverse-engineered from LabVIEW VIs:
- S1_parametetsSetting2017.vi
- S2_Motor_Set speed2015.vi
- S3Acq_fource_ai0.vi
- S3Motor_control2017m.vi
- S4_Youngs_Graph.vi
"""

from dataclasses import dataclass

@dataclass
class IndenterConfig:
    # --- Motor Serial Port Configuration (S2 / Speed setup) ---
    serial_port: str = "COM4"           # Default COM port
    baud_rate: int = 9600               # 9600 baud, 8N1
    serial_timeout: float = 1.0         # Seconds
    axis_id: str = "@0"                 # Station / Axis ID prefix

    # --- Speed Setup Parameters (@0SI start, top, accel) ---
    start_speed: int = 400              # Starting pulse frequency (pulses/s)
    top_speed: int = 1600               # Operating pulse frequency (found: 1600)
    accel_rate: int = 1600              # Acceleration/Deceleration ramp (found: 1600)

    # --- Indentation Kinematics (S1: 前進距離 & 前進STEP) ---
    steps_per_mm: float = 400.0         # Pulses per mm of vertical travel (e.g. 400 steps/mm)
    target_displacement_mm: float = 1.5 # Default indentation depth (1.0 - 2.0 mm)
    repeat_cycles: int = 5              # Number of cycles (proposal standard: 5 cycles)
    dwell_time_s: float = 0.5           # Hold / dwell duration at peak indentation (s)
    retract_time_s: float = 1.8         # Upward retraction duration (s)
    cycle_rest_s: float = 1.0           # Rest interval between cycles (s)

    # --- NI-DAQmx Configuration (S3Acq: Dev1/ai0) ---
    daq_channel: str = "Dev1/ai0"       # NI DAQ Physical Channel
    daq_sample_rate: float = 100.0      # Acquisition frequency (Hz)
    voltage_min: float = -10.0          # DAQ voltage range min (V)
    voltage_max: float = 10.0           # DAQ voltage range max (V)

    # --- Load Cell Force Calibration ---
    # Formula: Force (N) = (V_measured - V_tare) * force_calibration_factor
    force_calibration_factor: float = 10.0 # Newtons per Volt (N/V)
    tare_voltage_offset: float = 0.045     # Baseline offset voltage (V)

    # --- Young's Modulus Biomechanical Constants (Hayes 1972 / Zheng & Mak 1999) ---
    poisson_ratio: float = 0.45         # nu = 0.45 for biological soft tissue
    indenter_radius_mm: float = 4.5     # a = 4.5 mm (ultrasound transducer indenter tip)
    tissue_thickness_mm: float = 12.0   # h = typical Upper Trapezius muscle thickness (mm)

    # --- Elasticity Calculation Mode ---
    # Options: "matlab_polyfit" (legacy s3_e_20170718_polyfit_index_kUS.m) or "piecewise_linear"
    calculation_method: str = "matlab_polyfit"
    matlab_strain_ratios: tuple[float, float, float] = (0.05, 0.10, 0.15)

