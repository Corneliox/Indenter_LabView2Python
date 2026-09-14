# Automated Muscle Indenter System - Operational & Technical Workflows
> **Detailed Engineering Architecture, State Machines, Threading, and Clinical Protocols**

---

## 1. High-Level System Architecture Workflow

The system is structured as a decoupled, multi-tier pipeline ensuring high-frequency analog data acquisition is never interrupted by serial communications or UI rendering:

```mermaid
graph TD
    subgraph Hardware Layer
        Motor["Linear Stepper Motor (Actuator)"]
        LoadCell["Load Cell Force Sensor"]
        DAQ["NI-DAQ Card (ai0)"]
    end

    subgraph Communication & Driver Tier
        SerialDriver["MotorController (RS-232 / PySerial)<br/>@0SI, @0U, @0X, @0?"]
        DaqDriver["DaqReader (NI-DAQmx Thread)<br/>Tare Zeroing & 100 Hz Sampling"]
    end

    subgraph Orchestration Tier
        Pipeline["IndenterPipeline (Worker Thread)<br/>Cyclic State Machine (5 Cycles)"]
    end

    subgraph Analytical & Visualization Tier
        Youngs["Young's Modulus Engine<br/>Hayes 1972 (E1, E2, E3)"]
        GUI["IndenterApp (Tkinter GUI)<br/>Real-Time F-d Hysteresis & F-t Chart"]
        Logger["File Exporter<br/>Tab-Delimited TXT / CSV"]
    end

    Motor <-->|RS-232 ASCII| SerialDriver
    LoadCell -->|Analog mV| DAQ
    DAQ -->|Voltage Read| DaqDriver

    SerialDriver <--> Pipeline
    DaqDriver --> Pipeline

    Pipeline -->|Synchronized Records| GUI
    Pipeline -->|Completed Cycle Data| Youngs
    Youngs -->|E1, E2, E3 (kPa)| GUI
    Pipeline -->|Batch Records| Logger
```

---

## 2. Multi-Threaded Concurrency Model

To eliminate timing jitter and prevent serial latency from throttling the DAQ rate, three concurrent execution threads run in parallel:

```mermaid
sequenceDiagram
    autonumber
    participant GUI as Tkinter Main Thread (GUI & Plots)
    participant Seq as Pipeline Sequencer Thread
    participant DAQ as DAQ Reader Thread (100 Hz)
    participant Motor as Stepper Motor (Serial COM)

    Note over GUI,DAQ: System Initialization
    GUI->>DAQ: daq.start()
    activate DAQ
    Note over DAQ: Continuous Background Loop:<br/>Reads ai0, applies Tare offset,<br/>calculates Force in Newtons.

    GUI->>Motor: motor.connect() & set_speed(@0SI)
    GUI->>DAQ: daq.tare() (Averages baseline voltage)

    Note over GUI,Seq: User clicks "START TEST (啟動)"
    GUI->>Seq: run_experiment_async()
    activate Seq

    loop For each Cycle (1 to N)
        Note over Seq,Motor: Phase 1: Indentation (Loading, ~3.0s)
        Seq->>Motor: move_relative(@0U{steps})
        loop While Moving
            Seq->>DAQ: read_sample() -> (V, N)
            Seq->>Motor: query_position() -> (steps, mm)
            Seq->>Seq: Append timestamped record
            GUI->>GUI: GUI update loop draws live F-d curve
        end

        Note over Seq: Phase 2: Dwell Hold (0.5s)
        Seq->>Seq: High-speed sampling at peak depth

        Note over Seq,Motor: Phase 3: Retraction (Unloading, ~1.8s)
        Seq->>Motor: move_absolute(@0X0)
        loop While Retracting
            Seq->>DAQ: read_sample()
            Seq->>Motor: query_position()
            Seq->>Seq: Append unloading record
        end

        Note over Seq: Phase 4: Modulus Computation
        Seq->>Seq: Fit dP/dw slopes (E1, E2, E3)
        Seq-->>GUI: on_cycle_complete(cycle, results)
        GUI->>GUI: Update E1, E2, E3 display labels

        Note over Seq: Phase 5: Inter-Cycle Rest (1.0s)
        Seq->>Seq: Sleep rest interval
    end

    Seq-->>GUI: on_experiment_finish(overall_results)
    deactivate Seq
    GUI->>GUI: Show finish dialog & enable Export
```

---

## 3. Cyclic Indentation State Machine

Each complete test consists of standardized pressure cycles (typically 5 consecutive cycles) reproducing the mechanical indentation protocol of the clinical study:

```mermaid
stateDiagram-v2
    [*] --> Idle: Application Start

    Idle --> Configured: Set Depth, Speed, Cycles
    Configured --> Tared: Press "Tare Sensor" (Zero N)
    Tared --> Running: Press "START TEST"

    state Running {
        [*] --> Loading: Send @0U{steps}
        Loading --> Dwell: Target depth reached (w = 1.5 mm, ~3.0s)
        Dwell --> Unloading: Dwell timer expired (0.5s hold)
        Unloading --> Rest: Motor returned to Home (@0X0, ~1.8s)
        Rest --> Loading: Cycle < Repeat Cycles
        Rest --> Finished: Cycle == Repeat Cycles
    }

    Running --> Stopped: User clicks "STOP / ABORT"
    Stopped --> Idle: Safe return to Home
    Finished --> Idle: Young's Modulus Calculated & Displayed
```

---

## 4. Clinical & Operator Step-by-Step Protocol

This protocol guides biomedical engineers and clinicians through performing an indentation test on the Upper Trapezius muscle:

```mermaid
flowchart TD
    Step1["1. Pre-Therapy Subject Setup<br/>• Subject seated upright with neck in neutral position<br/>• Locate Upper Trapezius anatomical landmarks (Points A, B, C, or D)"]
    
    Step2["2. Ultrasound Baseline Thickness<br/>• Apply ultrasound gel to indenter contact probe<br/>• Position probe perpendicular (90°) to skin surface<br/>• Record baseline muscle thickness h (mm) via B-mode USG"]

    Step3["3. Hardware Check & Tare Calibration<br/>• Launch Python GUI: python indenter_gui.py<br/>• Verify COM port and DAQ channel<br/>• Click 'Tare Sensor (Zero N)' while probe is in air / feather-touch"]

    Step4["4. Protocol Configuration<br/>• Target Displacement: 1.0 - 2.0 mm (Standard: 1.5 mm)<br/>• Number of Cycles: 5 consecutive cycles<br/>• Loading Duration: 3.0 s | Dwell: 0.5 s | Unloading: 1.8 s"]

    Step5["5. Measurement Execution<br/>• Hold probe firmly at 90° against the muscle site<br/>• Click '▶ START TEST (啟動)'<br/>• Observe live F-d hysteresis loop and F-t curve"]

    Step6["6. Results Review & Export<br/>• Review calculated E1, E2, E3, and E_mean (kPa)<br/>• Click '💾 Export Data' to save tab-delimited file (.txt)<br/>• Clean probe and prepare next measurement location"]

    Step1 --> Step2 --> Step3 --> Step4 --> Step5 --> Step6
```

---

## 5. Young's Modulus Extraction & Analysis Pipeline

The Young's Modulus calculation translates raw discrete data points into clinically meaningful tissue stiffness values:

```mermaid
flowchart LR
    subgraph Data Ingestion
        Raw["Cyclic Time-Series Data<br/>(Displacement w, Force P)"]
    end

    subgraph Filtration & Segmentation
        Filter["Filter Loading Phase Only<br/>(Increasing w from 0 to w_max)"]
        Seg1["Strain Segment 1 (5% - 35% w_max)"]
        Seg2["Strain Segment 2 (35% - 70% w_max)"]
        Seg3["Strain Segment 3 (70% - 100% w_max)"]
    end

    subgraph Linear Regression
        Slope1["Slope 1: (dP/dw)_1"]
        Slope2["Slope 2: (dP/dw)_2"]
        Slope3["Slope 3: (dP/dw)_3"]
    end

    subgraph Hayes Geometry Correction
        Correction["Geometry Factor:<br/>G = (1 - ν²) / (2 · a · κ)<br/>where a=4.5mm, ν=0.45, κ=f(a/h)"]
    end

    subgraph Output Moduli
        E1["E1 (kPa): Initial elasticity"]
        E2["E2 (kPa): Muscle belly stiffness"]
        E3["E3 (kPa): Deep structural stiffness"]
    end

    Raw --> Filter
    Filter --> Seg1 --> Slope1
    Filter --> Seg2 --> Slope2
    Filter --> Seg3 --> Slope3

    Correction --> E1
    Correction --> E2
    Correction --> E3

    Slope1 --> E1
    Slope2 --> E2
    Slope3 --> E3
```

---

## 6. Simulation vs. Real Hardware Operational Workflow

To transition seamlessly between offline software development and physical lab testing:

```mermaid
flowchart TD
    Start([Launch indenter_gui.py]) --> CheckEnv{Physical DAQ &<br/>COM Port Connected?}
    
    CheckEnv -- No --> SimMode["Simulation Mode Automatically Engaged<br/>• Generates realistic synthetic viscoelastic muscle curves<br/>• Smooth motion interpolation across 3.0s loading<br/>• Full GUI & Export functionality active"]
    
    CheckEnv -- Yes --> RealMode["Real Hardware Mode<br/>• Uncheck 'Simulation Mode' in GUI<br/>• Select active COM Port (e.g. COM4)<br/>• Select DAQ Channel (e.g. Dev1/ai0)<br/>• Click 'Tare Sensor'"]
    
    SimMode --> TestRun[Execute Test & Review Results]
    RealMode --> TestRun
```
