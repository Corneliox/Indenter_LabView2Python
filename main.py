"""
Main Entry Point & Verification Runner for Indenter System
Can run in headless CLI test mode or launch full GUI.
"""

import sys
import time
import argparse
from config import IndenterConfig
from indenter_pipeline import IndenterPipeline


def run_cli_test(cycles: int = 2, displacement_mm: float = 1.5, export_file: str = "test_run.txt"):
    """Runs an automated test cycle in simulation mode to verify end-to-end functionality."""
    print("=" * 60)
    print("   AUTOMATED INDENTER SYSTEM - CLI SELF-TEST MODE")
    print("=" * 60)

    config = IndenterConfig(
        repeat_cycles=cycles,
        target_displacement_mm=displacement_mm
    )

    pipeline = IndenterPipeline(config, simulation_mode=True)
    pipeline.initialize()

    print(f"Target: {displacement_mm} mm across {cycles} cycles")
    print("Starting cyclic indentation sequencer...")

    pipeline.run_experiment_async()

    while pipeline.is_running:
        raw_v, force_n = pipeline.daq.read_sample()
        disp_mm = pipeline.motor.get_displacement_mm()
        step = pipeline.motor.current_step_pos
        print(f"\rCycle {pipeline.current_cycle}/{cycles} | Disp: {disp_mm:4.2f} mm ({step:4d} steps) | "
              f"Force: {force_n:5.3f} N ({raw_v:5.3f} V)", end="", flush=True)
        time.sleep(0.1)

    print("\n\nTest execution finished!")
    print(f"Total sampled points: {len(pipeline.data_records)}")

    # Export test results
    pipeline.export_data(export_file)
    pipeline.shutdown()
    print("Self-test completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indenter System Controller")
    parser.add_argument("--cli", action="store_true", help="Run automated CLI self-test without GUI")
    parser.add_argument("--cycles", type=int, default=2, help="Number of test cycles")
    parser.add_argument("--depth", type=float, default=1.5, help="Indentation depth in mm")
    parser.add_argument("--export", type=str, default="test_indenter_output.txt", help="Output file path")
    args = parser.parse_args()

    if args.cli:
        run_cli_test(cycles=args.cycles, displacement_mm=args.depth, export_file=args.export)
    else:
        from indenter_gui import IndenterApp
        app = IndenterApp()
        app.mainloop()
