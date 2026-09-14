# Automated Muscle Indenter System (Taiwan AU Project)
> **Modernized Python Suite for Biomechanical Indentation, Real-Time Force Acquisition & Young's Modulus Assessment**

---

## 1. Executive Summary

This project is a complete, modernized Python conversion of the legacy National Instruments LabVIEW suite originally developed for Upper Trapezius (UT) muscle stiffness diagnosis and therapeutic evaluation (e.g., Local Vibration Therapy / Botox intervention).

The system automates:
1. **Vertical Stepper Motor Micro-Actuation**: Precise cyclic indentation (1.0 – 5.0 mm).
2. **High-Frequency Force Acquisition (NI-DAQmx)**: Continuous analog sampling from the load cell amplifier (`ai0`), with zero-drift tare calibration and conversion to Newtons ($N$).
3. **Effective Young's Modulus Computation ($E_1, E_2, E_3$)**: Implementation of the Hayes et al. (1972) and Zheng & Mak (1999) cylindrical flat-punch elastic layer model.
4. **Real-Time Data Visualization & Logging**: Real-time plotting of the Force vs. Displacement ($F-d$) hysteresis loop and time-domain profiles ($F-t$, $d-t$), exporting to standard spreadsheet formats.

---

## 2. Architecture & LabVIEW Mapping

The suite replaces 5 legacy LabVIEW Virtual Instruments (`.vi`) and associated subVIs with a clean, decoupled, multi-threaded Python architecture:

```
Legacy LabVIEW VI Architecture                     Modern Modular Python Architecture
┌───────────────────────────────┐                  ┌─────────────────────────────────┐
│ S1_parametetsSetting2017.vi   │ ───────────────> │ config.py                       │
│ (Kinematic & Cyclic Settings) │                  │ (Configuration & Calibration)   │
├───────────────────────────────┤                  ├─────────────────────────────────┤
│ S2_Motor_Set speed2015.vi     │                  │                                 │
│ motorposi(SubVI).vi           │ ───────────────> │ motor_controller.py             │
│ motor absposi(SubVI).vi       │                  │ (RS-232 / VISA Serial Engine)   │
│ POSiReadout.vi                │                  │                                 │
├───────────────────────────────┤                  ├─────────────────────────────────┤
│ S3Acq_fource_ai0.vi           │ ───────────────> │ daq_reader.py                   │
│ (Analog Voltage Reading)      │                  │ (NI-DAQmx & Tare Zeroing Thread)│
├───────────────────────────────┤                  ├─────────────────────────────────┤
│ S3Motor_control2017m.vi       │ ───────────────> │ indenter_pipeline.py            │
│ (Motion & Sampling Sequencer) │                  │ (Threaded Cyclic State Machine) │
├───────────────────────────────┤                  ├─────────────────────────────────┤
│ S4_Youngs_Graph.vi            │ ───────────────> │ youngs_modulus.py               │
│ (XY Graph & Modulus Export)   │                  │ (Hayes 1972 Mathematical Model) │
└───────────────────────────────┘                  ├─────────────────────────────────┤
                                                   │ indenter_gui.py                 │
                                                   │ (Interactive Tkinter Dashboard) │
                                                   └─────────────────────────────────┘
```

---

## 3. Hardware Protocols & Interface Specifications

### A. Stepper Motor Controller (RS-232 Serial)
* **Default Port**: `COM4` (Configurable: `COM1` – `COM9`)
* **Baud Rate**: `9600` bps, 8 Data Bits, No Parity, 1 Stop Bit (`8N1`)
* **Command Syntax**:
  | Action | Command String | Description |
  | :--- | :--- | :--- |
  | **Set Speed** | `@0SI{start},{top},{accel}\r\n` | Configures starting frequency, operating frequency (default: 1600 pulses/s), and acceleration ramp. |
  | **Relative Move** | `@0U{steps}\r\n` | Advances the indenter forward by a relative step count (e.g. `@0U600` for 1.5 mm). |
  | **Absolute Move** | `@0X{position}\r\n` | Retracts the indenter to origin (`@0X0`) or references a preset point (`@0X2000`). |
  | **Read Position** | `@0?\r\n` | Queries controller register; parses incoming string `POSItion <value>`. |

### B. Load Cell & NI-DAQmx Interface
* **Interface**: National Instruments USB or PCIe DAQ Card (e.g., USB-6008, USB-6009, PCIe-6321)
* **Physical Channel**: `Dev1/ai0` (Configurable to `Dev2/ai0`, etc.)
* **Voltage Range**: $\pm 10\text{ V}$ (Differential or RSE terminal configuration)
* **Sampling Rate**: $100.0\text{ Hz}$ (Configurable up to $1000\text{ Hz}$)
* **Force Conversion Equation**:
  $$F\,(\text{N}) = \max\Big(0,\, \big(V_{\text{measured}} - V_{\text{tare}}\big) \times K_{\text{cal}}\Big)$$
  * $V_{\text{tare}}$: Baseline sensor offset voltage captured during zeroing (typically $\approx 0.045\text{ V}$).
  * $K_{\text{cal}}$: Sensitivity calibration factor in $\text{N/V}$ (default: $10.0\text{ N/V}$).

---

## 4. Theoretical Biomechanical Model

### Effective Young's Modulus ($E$)
For indentation of biological soft tissue layer bounded to a rigid bony substrate (Zheng & Mak 1999; Hayes et al. 1972):

$$E = \frac{1 - \nu^2}{2 \cdot a \cdot \kappa\left(\frac{a}{h}, \nu\right)} \cdot \left(\frac{\Delta P}{\Delta w}\right)$$

Where:
* $\nu = 0.45$: Poisson's ratio for human skeletal muscle.
* $a = 4.5\text{ mm} = 0.0045\text{ m}$: Radius of the cylindrical indenter tip (ultrasound probe contact surface).
* $h = 12.0\text{ mm}$: Baseline muscle thickness measured via B-mode ultrasound.
* $\kappa\left(\frac{a}{h}, \nu\right) \approx 1.0 + 0.65\left(\frac{a}{h}\right) + 0.20\left(\frac{a}{h}\right)^2$: Hayes finite-thickness scaling correction factor.
* $\frac{\Delta P}{\Delta w}$: Slope of the Force-Displacement curve ($\text{N/m}$) during the loading phase.

### Segmented Elasticity Analysis ($E_1, E_2, E_3$)
To capture the non-linear, viscoelastic stiffening of human muscle, the loading curve is split into 3 distinct strain regions:
1. **$E_1$ (Initial Contact / Toe Region, 5%–35% depth)**: Represents initial skin and subcutaneous fat deformation.
2. **$E_2$ (Linear Deformation Region, 35%–70% depth)**: Primary muscle belly elasticity.
3. **$E_3$ (High-Compression / Deep Tissue Region, 70%–100% depth)**: Fascial and deep bony-proximity stiffening.

---

## 5. Directory Structure

```
Indenter_Project/main/
│
├── config.py              # Central parameter definitions & biomechanical constants
├── daq_reader.py          # Background DAQ acquisition & Tare zero-calibration engine
├── motor_controller.py    # RS-232 serial driver & kinematic simulation
├── youngs_modulus.py      # Hayes 1972 mathematical modulus fitting
├── indenter_pipeline.py   # Asynchronous multi-cycle experiment sequencer
├── indenter_gui.py        # Complete Tkinter graphical dashboard
├── main.py                # Command-line runner & self-test launcher
│
├── README.md              # Technical manual and specifications (this file)
└── WORKFLOW.md            # Detailed operational and dataflow workflows
```

---

## 6. Installation & Quick Start

### Prerequisites
* Windows 10 / 11 with Python 3.10+
* NI-DAQmx Drivers (if connecting to physical NI DAQ hardware)

### Package Installation
```bash
pip install pyserial nidaqmx numpy pandas matplotlib scipy
```

> [!NOTE]
> If `nidaqmx` or `pyserial` are not installed, the software **automatically falls back to Simulation Mode**. This allows you to test the GUI, design protocols, and analyze synthetic biomechanical curves without needing physical hardware.

### Running the Graphical Dashboard (GUI)
```bash
python indenter_gui.py
```

### Running Automated CLI Self-Test (Headless / Offline)
To run an automated test (e.g., 2 cycles to 1.5 mm) and verify system integrity:
```bash
python main.py --cli --cycles 2 --depth 1.5 --export test_verification.txt
```

---

## 7. Data Logging & Output Format

The output file format directly replicates and extends the legacy LabVIEW spreadsheet output (`NOAH8010BEFORETA1`):

* **Delimiter**: Tab-separated (`\t`)
* **Numeric Format**: 3 decimal precision (`%.3f`)
* **Column Specification**:
  1. `timestamp_ms`: Elapsed experiment time in milliseconds.
  2. `step_pos`: Actuator position in integer encoder steps (`iSTEP`).
  3. `disp_mm`: Vertical displacement in millimeters ($w$).
  4. `raw_voltage_v`: Raw analog input voltage from DAQ (`Fource_LoadCell (V)`).
  5. `force_n`: Calibrated contact force in Newtons ($P$).
  6. `cycle`: Active cyclic index (1 through $N$).
