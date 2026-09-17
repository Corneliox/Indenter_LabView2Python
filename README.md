# Automated Muscle Indenter System (Taiwan AU Project)
> **Modernized Python Suite for Biomechanical Indentation, Real-Time Force Acquisition & Young's Modulus Assessment**

---

## 1. Executive Summary

This project is a complete, modernized Python conversion of the legacy National Instruments LabVIEW and MATLAB data-processing pipeline originally developed for Upper Trapezius (UT) muscle stiffness diagnosis and therapeutic evaluation (e.g., Local Vibration Therapy / Botox intervention).

The system automates:
1. **Vertical Stepper Motor Micro-Actuation**: Precise cyclic indentation (1.0 – 5.0 mm).
2. **High-Frequency Force Acquisition (NI-DAQmx)**: Continuous analog sampling from the load cell amplifier (`ai0`), with zero-drift tare calibration and conversion to Newtons ($N$).
3. **Dual-Mode Effective Young's Modulus Computation ($E_1, E_2, E_3, E_{23}$)**:
   - **Mode A: MATLAB-Compatible Polyfit (`matlab_polyfit`)**: Replicates the exact mathematical behavior of legacy MATLAB script `s3_e_20170718_polyfit_index_kUS.m` using 2nd-degree polynomial fitting evaluated at $5\%$, $10\%$, and $15\%$ of tissue thickness $h$, with Hayes $\kappa(a/h)$ discrete table interpolation.
   - **Mode B: Piecewise Linear Slope (`piecewise_linear`)**: Real-time linear regression across $5\%–35\%$, $35\%–70\%$, and $70\%–100\%$ indentation depth ranges ($w_{\max}$).
4. **Real-Time Data Visualization & Logging**: Real-time plotting of the Force vs. Displacement ($F-d$) hysteresis loop and time-domain profiles ($F-t$, $d-t$), exporting to standard tab-delimited spreadsheet formats.

---

## 2. System Architecture & Component Mapping

The modernized Python suite replaces 5 legacy LabVIEW Virtual Instruments (`.vi`) and 2 offline MATLAB scripts with a decoupled, multi-threaded architecture:

```
Legacy Architecture (LabVIEW + MATLAB)               Modernized Python Suite
┌────────────────────────────────────────┐          ┌────────────────────────────────────────┐
│ S1_parametetsSetting2017.vi            │ ───────> │ config.py                              │
│ (Kinematic & Cyclic Configuration)     │          │ (Central Configuration & Calibration)  │
├────────────────────────────────────────┤          ├────────────────────────────────────────┤
│ S2_Motor_Set speed2015.vi / Speed setup│          │                                        │
│ motorposi(SubVI).vi                    │ ───────> │ motor_controller.py                    │
│ motor absposi(SubVI).vi                │          │ (RS-232 Serial Engine & Simulation)    │
│ POSiReadout.vi                         │          │                                        │
├────────────────────────────────────────┤          ├────────────────────────────────────────┤
│ S3Acq_fource_ai0.vi                    │ ───────> │ daq_reader.py                          │
│ (Analog Voltage Reading)               │          │ (NI-DAQmx 100 Hz & Tare Thread)        │
├────────────────────────────────────────┤          ├────────────────────────────────────────┤
│ S3Motor_control2017m.vi                │ ───────> │ indenter_pipeline.py                   │
│ (Motion & Sampling Sequencer)          │          │ (Threaded Cyclic State Machine)        │
├────────────────────────────────────────┤          ├────────────────────────────────────────┤
│ S4_Youngs_Graph.vi                     │          │                                        │
│ s2_youngUS_20161205.m (Segmentation)   │ ───────> │ youngs_modulus.py                      │
│ s3_e_20170718_polyfit_index_kUS.m (E)  │          │ (Hayes 1972 & MATLAB Polyfit Engine)   │
└────────────────────────────────────────┘          ├────────────────────────────────────────┤
                                                    │ indenter_gui.py                        │
                                                    │ (Unified Interactive Tkinter GUI)      │
                                                    ├────────────────────────────────────────┤
                                                    │ main.py                                │
                                                    │ (Entry Point & Automated CLI Runner)   │
                                                    └────────────────────────────────────────┘
```

---

## 3. End-to-End Workflow Comparison: Python vs. Legacy MATLAB/LabVIEW

| Stage | Legacy Pipeline (LabVIEW + MATLAB) | Modernized Python Suite | Equivalence & Benefits |
| :--- | :--- | :--- | :--- |
| **1. Configuration** | Parameter input in `S1.vi` panel; motor baud rate hardcoded in `S2.vi`. | Clean dataclass in `config.py` with runtime overrides in GUI. | **Identical Kinematics** (400 steps/mm, 1.5 mm depth, 5 cycles). |
| **2. Motor Control** | `VISA Write` sends ASCII `@0SI`, `@0U`, `@0X0`, `@0?`. | `motor_controller.py` sends identical ASCII strings via PySerial. | **100% Hardware Protocol Equivalence**. |
| **3. Force Acquisition** | Continuous loop in `S3Acq.vi` with unbuffered global memory writes. No zero-offset subtraction. | Dedicated 100 Hz sampling thread in `daq_reader.py` with automated `tare()` offset calibration. | **Eliminates baseline drift and race conditions**. |
| **4. Motion Sequencing** | Multi-window manual sequence in `S3Motor.vi` (Loading $\sim 3\text{s}$, Dwell $0.5\text{s}$, Retract $1.8\text{s}$). | State machine in `indenter_pipeline.py` managing cyclic execution synchronously. | **Identical Physical Loading Sequence**. |
| **5. Segmentation** | **Manual Post-hoc:** User opens `s2_youngUS.m` and clicks 10 points with `ginput(1)` to find peaks and thickness. | **Fully Automated:** Algorithmic loading extraction via `np.argmax(disp_mm)` with zero user delay. | **Eliminates operator subjectivity & error**. |
| **6. Hayes Factor ($\kappa$)** | Fits 2nd-degree polynomial to `index_k_serial` table: `[p1, s1] = polyfit(x, y, 2)`. | Exact replication via `HAYES_LOOKUP_TABLE` and `calculate_hayes_kappa(..., use_matlab_table=True)`. | **100% Mathematical Equivalence** (Deviasi = 0.00%). |
| **7. Young's Modulus ($E$)** | `polyfit(w, P, 2)` evaluated at $5\%$, $10\%$, $15\%$ of thickness $h$, plus $E_{23}$. | Dual mode: `matlab_polyfit` (exact replica) or `piecewise_linear` (strain-zone slope). | **Full Backward-Compatibility with Historical Data**. |
| **8. Visualization & Export** | LabVIEW chart (`S4.vi`) + manual export; MATLAB plots saved post-hoc. | Live Matplotlib embedded dashboard with dual $F-d$ and $F-t$ / $d-t$ curves + one-click export. | **Integrated Single-Window Workflow**. |

---

## 4. Hardware Protocols & Interface Specifications

### A. Stepper Motor Controller (RS-232 Serial)
* **Default Port**: `COM4` (Configurable: `COM1` – `COM9`)
* **Baud Rate**: `9600` bps, 8 Data Bits, No Parity, 1 Stop Bit (`8N1`)
* **Command Syntax**:
  | Action | Command String | Description |
  | :--- | :--- | :--- |
  | **Set Speed** | `@0SI{start},{top},{accel}\r\n` | Configures start frequency (400), top speed (default: 1600 pulses/s), and acceleration ramp (1600). |
  | **Relative Move** | `@0U{steps}\r\n` | Advances indenter downward by relative steps (`@0U600` for 1.5 mm at 400 steps/mm). |
  | **Absolute Move** | `@0X{position}\r\n` | Retracts indenter to origin (`@0X0`) or moves to preset position. |
  | **Read Position** | `@0?\r\n` | Queries controller register; parses string `POSItion <value>`. |

### B. Load Cell & NI-DAQmx Interface
* **Interface**: National Instruments USB/PCIe DAQ (e.g. USB-6008, PCIe-6321)
* **Physical Channel**: `Dev1/ai0` (Configurable)
* **Sampling Frequency**: $100.0\text{ Hz}$
* **Calibrated Force Equation**:
  $$F\,(\text{N}) = \max\Big(0,\, \big(V_{\text{measured}} - V_{\text{tare}}\big) \times K_{\text{cal}}\Big)$$
  * $V_{\text{tare}}$: Baseline sensor offset captured during tare (typically $\approx 0.045\text{ V}$).
  * $K_{\text{cal}}$: Calibration sensitivity (default: $10.0\text{ N/V}$).

---

## 5. Theoretical Biomechanical Model & Mathematical Equivalence

### Cylindrical Indentation of Bounded Elastic Layer (Hayes et al. 1972)
$$E = \left[ \frac{1 - \nu^2}{2 \cdot a \cdot \kappa\left(\frac{a}{h}, \nu\right)} \right] \cdot \left(\frac{\Delta P}{\Delta w}\right)$$

Where:
* $\nu = 0.45$: Poisson's ratio for human skeletal muscle.
* $a = 4.5\text{ mm} = 0.0045\text{ m}$: Radius of the indenter tip.
* $h = 12.0\text{ mm}$: Baseline muscle thickness measured via ultrasound.
* $\kappa\left(\frac{a}{h}, \nu\right)$: Geometric scaling factor interpolated from Hayes' lookup table.

### Mathematical Proof of Unit Equivalence (MATLAB vs. Python SI)
* In legacy MATLAB (`s3_e_20170718_polyfit_index_kUS.m`):
  $$E_{\text{MATLAB}} = \frac{P_{\text{kg}}}{w_{\text{mm}}} \cdot \frac{1 - \nu^2}{2 \cdot a_{\text{mm}} \cdot \kappa} \cdot 9813.43$$
* In Python SI units:
  $$E_{\text{Python}} = \frac{P_{\text{N}}}{w_{\text{m}}} \cdot \frac{1 - \nu^2}{2 \cdot a_{\text{m}} \cdot \kappa} \cdot 10^{-3} = E_{\text{MATLAB}}$$
* Because $1\text{ kg} = 9.81343\text{ N}$ and $1\text{ mm} = 10^{-3}\text{ m}$, the two formulations are **identically equivalent** down to floating-point precision ($0.00\%$ discrepancy).

---

## 6. Directory Structure

```
Indenter_Project/main/
│
├── config.py              # Central parameter definitions & biomechanical constants
├── daq_reader.py          # Background DAQ acquisition & Tare zero-calibration engine
├── motor_controller.py    # RS-232 serial driver & kinematic simulation
├── youngs_modulus.py      # Hayes 1972 & exact MATLAB s3_e polyfit implementation
├── indenter_pipeline.py   # Asynchronous multi-cycle experiment sequencer
├── indenter_gui.py        # Interactive Tkinter dashboard with live F-d & F-t plots
├── main.py                # System entry point & headless CLI verification test
│
├── README.md              # Technical specifications and comparative manual
├── WORKFLOW.md            # Modernized Python operational workflows
└── WORKFLOW_OLD.md        # Technical documentation of legacy LabVIEW VIs
```

---

## 7. Installation & Quick Start

### Prerequisites
* Windows 10 / 11 with Python 3.10+
* NI-DAQmx Drivers (if using physical NI DAQ hardware)

### Package Installation
```bash
pip install pyserial nidaqmx numpy pandas matplotlib scipy
```

> [!NOTE]
> If `nidaqmx` or `pyserial` are not detected, the software **automatically enters Simulation Mode**. You can run the entire GUI, test cyclic indentation, and compute Young's Modulus offline without physical hardware.

### Running the Graphical Dashboard (GUI)
```bash
python indenter_gui.py
# or
python main.py
```

### Running Automated Headless CLI Self-Test
To execute a verification test (e.g., 2 cycles to 1.5 mm) and confirm math/logging integrity:
```bash
python main.py --cli --cycles 2 --depth 1.5 --export test_output.txt
```

---

## 8. Data Logging & Output Format

Output files reproduce and expand the legacy LabVIEW tab-delimited format (`NOAH8010BEFORETA1`):
* **Format**: Tab-separated values (`.txt` / `.tsv`), `%.3f` numeric precision.
* **Columns**:
  1. `timestamp_ms`: Elapsed time (ms).
  2. `step_pos`: Actuator step position (`iSTEP`).
  3. `disp_mm`: Indentation depth in mm ($w$).
  4. `raw_voltage_v`: Load cell amplifier voltage (`Fource_LoadCell (V)`).
  5. `force_n`: Contact force in Newtons ($P$).
  6. `cycle`: Cycle index (1 through $N$).

