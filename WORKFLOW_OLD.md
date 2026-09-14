# Legacy LabVIEW Indenter Suite - Architecture & Operational Workflow
> **Technical Documentation of Legacy National Instruments LabVIEW VIs (AU Taiwan Indenter Project)**

---

## 1. Overview of the Legacy LabVIEW Suite

The legacy system consists of five standalone National Instruments LabVIEW Virtual Instruments (`.vi`) and four specialized subVIs. Inter-VI communication and synchronization rely entirely on a LabVIEW **Global Variable** (`2015myGlobal 1.vi`) residing in shared memory.

### Original Execution Order (from `README.txt`)
To operate the legacy system, the operator had to open and manually run four separate VI windows simultaneously:
```
1. S1_parametetsSetting2017.vi   (Define kinematics and cycle parameters)
2. S2_Motor_Set speed2015.vi     (Initialize motor speed over VISA serial)
3. S3Acq_fource_ai0.vi           (Start continuous analog DAQ reading loop)
4. S3Motor_control2017m.vi       (Execute the physical cyclic indentation sequence)
5. S4_Youngs_Graph.vi            (Live XY graph plotting & spreadsheet file export)
```

---

## 2. Legacy System Architecture Diagram

```mermaid
graph TD
    subgraph Memory Shared Pool
        GlobalVI["2015myGlobal 1.vi<br/>(LabVIEW Global Variable Pool)<br/>• iSTEP (Motor Position)<br/>• Fource_LoadCell (V)<br/>• Repeat Cycles, Dwell, Speed"]
    end

    subgraph VI 1: Parameter Setup
        S1["S1_parametetsSetting2017.vi<br/>Front Panel Inputs:<br/>Target mm, Steps, Cycles, Dwell"]
    end

    subgraph VI 2: Motor Velocity Setup
        S2["S2_Motor_Set speed2015.vi<br/>Speed setup.vi<br/>Configure VISA Port COM4, 9600 8N1"]
        VISAWrite["VISA Write (TL3T)<br/>Send: @0SI1600,1600,1600"]
    end

    subgraph VI 3: DAQ Continuous Acquisition
        S3Acq["S3Acq_fource_ai0.vi<br/>Continuous While Loop (DAQmx)<br/>Physical Channel: Dev1/ai0"]
        DAQRead["DAQmx Read 1Chan 1Samp<br/>Analog Voltage Basic"]
    end

    subgraph VI 4: Motion Sequencer
        S3Motor["S3Motor_control2017m.vi<br/>Main Motion Loop (Cycles 1 to N)"]
        SubPosi["motorposi(SubVI).vi<br/>Send: @0U{steps}"]
        SubDwell["Flat Sequence: Dwell Hold (s)"]
        SubAbs["motor absposi(SubVI).vi<br/>Send: @0X0 (Retract)"]
        SubRead["POSiReadout.vi<br/>Send: @0? -> Scan POSItion"]
    end

    subgraph VI 5: Graphing and Logging
        S4["S4_Youngs_Graph.vi<br/>While Loop Chart Display"]
        XYChart["Chart of Fource and Dislpacement<br/>(Voltage vs iSTEP)"]
        WriteFile["Write To Spreadsheet File (DBL)<br/>Export: NOAH8010 Tab-Separated TXT"]
    end

    S1 -->|"Write Parameters"| GlobalVI
    S2 --> VISAWrite
    VISAWrite -->|"Set Initial Velocity"| GlobalVI

    DAQRead -->|"Continuous Write: Fource_LoadCell (V)"| GlobalVI
    S3Acq --> DAQRead

    GlobalVI -->|"Read Target Steps and Dwell"| S3Motor
    S3Motor --> SubPosi
    SubPosi --> SubDwell
    SubDwell --> SubAbs
    SubAbs --> SubRead
    SubRead -->|"Write Updated Position: iSTEP"| GlobalVI

    GlobalVI -->|"Read iSTEP and Voltage"| S4
    S4 --> XYChart
    S4 --> WriteFile
```

---

## 3. Legacy Inter-VI Dataflow & Sequence Workflow

Because the legacy suite lacked a centralized state machine or thread manager, execution relied on manual operator coordination across parallel VI windows:

```mermaid
sequenceDiagram
    autonumber
    participant Op as Human Operator
    participant S1 as S1_parametetsSetting2017.vi
    participant S2 as S2_Motor_Set speed2015.vi
    participant Mem as "2015myGlobal 1.vi (Global Memory)"
    participant S3A as "S3Acq_fource_ai0.vi (DAQ Loop)"
    participant S3M as "S3Motor_control2017m.vi (Motor Loop)"
    participant S4 as "S4_Youngs_Graph.vi (Plotter/Logger)"
    participant HW as "Hardware (Motor and DAQ)"

    Note over Op,S1: Step 1: Input Test Parameters
    Op->>S1: Enter target depth (mm), steps, cycles, dwell
    S1->>Mem: Write kinematics into global variables

    Note over Op,S2: Step 2: Initialize Motor Velocity
    Op->>S2: Run S2 VI
    S2->>HW: VISA Write: @0SI1600,1600,1600
    S2->>Mem: Write speed confirmation

    Note over Op,S3A: Step 3: Launch Analog DAQ Loop
    Op->>S3A: Run S3Acq VI
    loop Continuous DAQ While Loop
        S3A->>HW: DAQmx Read (Dev1/ai0)
        HW-->>S3A: Return raw analog voltage (V)
        S3A->>Mem: Overwrite Fource_LoadCell (V)
    end

    Note over Op,S4: Step 4: Open Real-Time Graphing
    Op->>S4: Run S4 VI
    Note over S4: S4 enters listening loop, polling global memory

    Note over Op,S3M: Step 5: Trigger Physical Indentation
    Op->>S3M: Run S3Motor VI
    S3M->>Mem: Set Running Flag (啟動中 = True)

    loop For each Cycle (1 to Repeat Cycles)
        Note over S3M,HW: Forward Loading Phase
        S3M->>HW: Call motorposi -> Send @0U steps
        S3M->>HW: Call POSiReadout -> Read current step
        S3M->>Mem: Update iSTEP in global memory

        Note over S3M: Sequence Pause: Dwell Hold (s)

        Note over S3M,HW: Retraction Unloading Phase
        S3M->>HW: Call motor absposi -> Send @0X0 (Home)
        S3M->>HW: Call POSiReadout -> Read zero position
        S3M->>Mem: Update iSTEP in global memory

        Note over S4: S4 reads iSTEP and Voltage asynchronously
        S4->>Mem: Read iSTEP and Fource_LoadCell (V)
        S4->>S4: Plot XY point on Chart
        S4->>HW: Write To Spreadsheet File (iSTEP and Voltage)
    end

    S3M->>Mem: Set Running Flag (啟動中 = False)
    Op->>S4: Stop S4 and save completed spreadsheet
```

---

## 4. Breakdown of Legacy Virtual Instruments (VIs)

### 1. `S1_parametetsSetting2017.vi`
* **Purpose**: Front panel configuration utility.
* **Key Controls**:
  * `前進距離(mm)`: Forward displacement in millimeters.
  * `前進STEP`: Target step count (calculated as $\text{mm} \times \text{steps\_per\_mm}$).
  * `重複次數`: Number of repeat indentation cycles.
  * `速度參數`: Motor pulse frequency.
  * `停留時間(秒)`: Dwell / hold duration at peak compression.
  * `上升時間(秒)`: Retraction duration.
  * `millisecond multiple`: Loop timing delay for LabVIEW scheduler.
* **Mechanism**: Direct unbuffered writes to `2015myGlobal 1.vi`.

### 2. `S2_Motor_Set speed2015.vi` / `Speed setup.vi`
* **Purpose**: Serial driver initialization.
* **VISA Configuration**:
  * Port: `COM4` (or selectable `COM3`/`COM9`), Baud: `9600`, Data: `8`, Parity: `None`, Stop: `1`.
  * Termination Character: `0xA` (`\n` Line Feed).
* **Command Syntax**:
  * Formats ASCII string: `@0SI{start},{top},{accel}\r\n` (e.g., `@0SI1600,1600,1600\r\n`).
  * Writes to VISA serial resource via subVI `VISA Write in Serial Communication for TL3T of VISA.vi`.

### 3. `S3Acq_fource_ai0.vi`
* **Purpose**: Analog voltage acquisition from load cell amplifier.
* **NI-DAQmx Task**:
  * Function: `DAQmx Create Channel (AI-Voltage-Basic)`.
  * Channel: `Dev1/ai0` (or `Dev2/ai0`).
  * Terminal Configuration: `DEFAULT`.
  * Acquisition Mode: `Analog DBL 1Chan 1Samp` in a tight While Loop.
* **Output**: Constantly overwrites global variable `Fource_LoadCell (V)` in memory.

### 4. `S3Motor_control2017m.vi`
* **Purpose**: Hardware motion coordination using 3 specialized subVIs:
  * **`motorposi(SubVI).vi`**: Sends `@0U{steps}\r\n` to advance the stepper motor.
  * **`motor absposi(SubVI).vi`**: Sends `@0X0\r\n` to return to home/retract.
  * **`POSiReadout.vi`**: Sends query `@0?\r\n`, reads serial response line, and scans string `POSItion <value>` to retrieve integer encoder pulses, writing to `iSTEP`.

### 5. `S4_Youngs_Graph.vi`
* **Purpose**: Visualization and raw data file logging.
* **Mechanism**:
  * Reads `iSTEP` and `Fource_LoadCell (V)` from `2015myGlobal 1.vi`.
  * Plots raw voltage versus displacement steps on `Chart of Fource & Dislpacement`.
  * Calls `Write To Spreadsheet File (DBL).vi` with `delimiter (\t)` and format `%.3f`.
  * Generates output data rows matching legacy format (`NOAH8010BEFORETA1`):
    ```text
    1000.000\t0.049\r\n
    1000.000\t0.050\r\n
    ```

---

## 5. Known Bottlenecks and Flaws of the Legacy LabVIEW Suite

Understanding the architectural limitations of the legacy LabVIEW suite illustrates why the Python migration was required:

1. **Global Variable Race Conditions**:
   * `S3Acq` wrote voltage into `2015myGlobal 1.vi` at high frequency, while `S3Motor` wrote `iSTEP` at low frequency over serial.
   * `S4` read both variables independently without thread synchronization or mutual exclusion (mutex). If `S4` read before `S3Motor` updated, multiple identical displacement steps were logged against changing voltages, distorting the $F-d$ curve.
2. **Missing Sensor Tare / Zero Offset Calibration**:
   * The legacy suite saved raw voltage directly without a baseline zeroing routine. As ambient temperature or initial probe resting pressure shifted (e.g. $0.042\text{ V} - 0.050\text{ V}$ baseline drift), the resulting force and elasticity calculations incurred large offsets.
3. **No Automated Young's Modulus Calculation**:
   * The legacy VI only plotted raw Voltage vs. Step count. To calculate Young's Modulus ($E_1, E_2, E_3$), researchers had to manually copy the spreadsheet files into external MATLAB scripts (e.g. Melani 2013 / Firda 2019 scripts) after the experiment finished.
4. **Manual Multi-Window Operator Burden**:
   * The operator had to open, position, and start 4 separate LabVIEW windows in exact sequence. If one window failed to start, the system could drive the motor without acquiring force data, risking tissue overload or actuator stalls.
