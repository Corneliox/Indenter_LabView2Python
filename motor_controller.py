"""
Stepper Motor Controller Module
Replaces:
- S2_Motor_Set speed2015.vi / Speed setup.vi (@0SI)
- motorposi(SubVI).vi (@0U)
- motor absposi(SubVI).vi (@0X)
- POSiReadout.vi (Position query and parsing)

Communicates via RS-232 / VISA COM port.
Includes high-fidelity simulated kinematics fallback.
"""

import time
import re
from typing import Optional
from config import IndenterConfig

# Try importing pyserial
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class MotorController:
    def __init__(self, config: IndenterConfig, simulation_mode: bool = False):
        self.config = config
        self.simulation_mode = simulation_mode or (not SERIAL_AVAILABLE)
        
        self.ser: Optional["serial.Serial"] = None
        self.current_step_pos: int = 0
        self.current_disp_mm: float = 0.0

        # Kinematic state for smooth simulation interpolation
        self._sim_start_pos: int = 0
        self._sim_target_pos: int = 0
        self._sim_move_start_time: float = 0.0
        self._sim_move_duration: float = 0.0
        self._sim_is_moving: bool = False

    def connect(self) -> bool:
        """Connect to the motor serial port."""
        if self.simulation_mode:
            print(f"[Motor] Running in SIMULATION MODE (Port {self.config.serial_port})")
            return True

        try:
            self.ser = serial.Serial(
                port=self.config.serial_port,
                baudrate=self.config.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.config.serial_timeout
            )
            time.sleep(0.1)
            # Initialize speed parameters matching S2 / Speed setup
            self.set_speed(
                self.config.start_speed,
                self.config.top_speed,
                self.config.accel_rate
            )
            return True
        except Exception as e:
            print(f"[Motor Warning] Serial connection error ({e}). Switching to simulation mode.")
            self.simulation_mode = True
            return True

    def disconnect(self):
        """Close serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_command(self, cmd: str) -> str:
        """Send raw command string to motor controller and read reply."""
        if self.simulation_mode:
            return "OK"

        if not self.ser or not self.ser.is_open:
            return ""

        formatted_cmd = cmd.strip() + "\r\n"
        self.ser.write(formatted_cmd.encode("ascii"))
        self.ser.flush()

        try:
            line = self.ser.readline().decode("ascii", errors="ignore").strip()
            return line
        except Exception:
            return ""

    def set_speed(self, start_spd: int, top_spd: int, accel: int) -> bool:
        """
        Reverse-engineered from S2_Motor_Set speed2015.vi & Speed setup.vi:
        Command format: @0SI{start},{top},{accel}
        """
        cmd = f"{self.config.axis_id}SI{start_spd},{top_spd},{accel}"
        self.send_command(cmd)
        return True

    def move_relative(self, steps: int, duration_s: float = 3.0) -> bool:
        """
        Reverse-engineered from motorposi(SubVI).vi:
        Command format: @0U{steps}
        """
        cmd = f"{self.config.axis_id}U{steps}"
        self.send_command(cmd)

        if self.simulation_mode:
            self._sim_start_pos = self.current_step_pos
            self._sim_target_pos = self.current_step_pos + steps
            self._sim_move_start_time = time.perf_counter()
            self._sim_move_duration = duration_s
            self._sim_is_moving = True
        else:
            self.current_step_pos += steps
            self.current_disp_mm = self.current_step_pos / self.config.steps_per_mm

        return True

    def move_absolute(self, target_pos: int = 0, duration_s: float = 1.8) -> bool:
        """
        Reverse-engineered from motor absposi(SubVI).vi:
        Command format: @0X{pos}
        """
        cmd = f"{self.config.axis_id}X{target_pos}"
        self.send_command(cmd)

        if self.simulation_mode:
            self._sim_start_pos = self.current_step_pos
            self._sim_target_pos = target_pos
            self._sim_move_start_time = time.perf_counter()
            self._sim_move_duration = duration_s
            self._sim_is_moving = True
        else:
            self.current_step_pos = target_pos
            self.current_disp_mm = self.current_step_pos / self.config.steps_per_mm

        return True

    def query_position(self) -> int:
        """
        Reverse-engineered from POSiReadout.vi:
        Queries encoder/stepper register and parses 'POSItion <val>'.
        In simulation mode, smoothly interpolates position across time.
        """
        if self.simulation_mode:
            if self._sim_is_moving:
                elapsed = time.perf_counter() - self._sim_move_start_time
                if elapsed >= self._sim_move_duration:
                    self.current_step_pos = self._sim_target_pos
                    self._sim_is_moving = False
                else:
                    progress = elapsed / self._sim_move_duration
                    self.current_step_pos = int(
                        self._sim_start_pos + (self._sim_target_pos - self._sim_start_pos) * progress
                    )
            self.current_disp_mm = self.current_step_pos / self.config.steps_per_mm
            return self.current_step_pos

        # Real hardware query
        resp = self.send_command(f"{self.config.axis_id}?")
        if not resp:
            return self.current_step_pos

        match = re.search(r"[-+]?\d+", resp)
        if match:
            pos = int(match.group(0))
            self.current_step_pos = pos
            self.current_disp_mm = pos / self.config.steps_per_mm
            return pos

        return self.current_step_pos

    def get_displacement_mm(self) -> float:
        """Returns current displacement in mm."""
        # Query position to ensure simulated interpolation updates
        self.query_position()
        return self.current_disp_mm
