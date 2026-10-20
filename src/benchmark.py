"""Menjalankan eksperimen scaling dan menyimpan hasil yang dapat diulang."""

from __future__ import annotations

import argparse
import multiprocessing
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

import matplotlib
import numpy as np
import pandas as pd
import psutil

from workload import WorkloadResult, run_parallel, run_serial

DEFAULT_SEED = 20261020
DEFAULT_SCENARIOS = 16
DEFAULT_SAMPLES_PER_SCENARIO = 40_000
DEFAULT_SCENARIOS_PER_PROCESS = 2
DEFAULT_REPEATS = 5


def physical_core_count() -> int:
    """Mendapatkan jumlah core fisik untuk menyusun konfigurasi default."""
    cores = psutil.cpu_count(logical=False)
    if cores is None or cores < 1:
        raise RuntimeError("Jumlah core fisik tidak dapat dideteksi oleh psutil.")
    return cores


def cpu_model() -> str:
    """Membaca nama CPU dari Windows atau memakai identifikasi platform."""
    if sys.platform == "win32":
        import winreg

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor() or platform.machine()

def default_process_counts(physical_cores: int) -> list[int]:
    """Menghasilkan skala 1, 2, 4, ... dan menyertakan core maksimum."""
    counts = [1]
    candidate = 2
    while candidate < physical_cores:
        counts.append(candidate)
        candidate *= 2
    if physical_cores > 1:
        counts.append(physical_cores)
    return counts


def device_metadata() -> dict[str, object]:
    """Merekam spesifikasi mesin dan versi Python/pustaka secara otomatis."""
    memory_gib = psutil.virtual_memory().total / (1024**3)
    return {
        "cpu": cpu_model(),
        "physical_cores": physical_core_count(),
        "logical_processors": psutil.cpu_count(logical=True),
        "ram_gib": round(memory_gib, 2),
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "matplotlib_version": matplotlib.__version__,
        "psutil_version": psutil.__version__,
    }


def measure(
    runner: Callable[[], WorkloadResult], repeats: int
) -> tuple[float, float, WorkloadResult]:
    """Mengukur pengulangan dan memastikan hasilnya deterministik."""
    durations: list[float] = []
    reference: WorkloadResult | None = None

    for _ in range(repeats):
        start = time.perf_counter()
        result = runner()
        durations.append(time.perf_counter() - start)
        if reference is None:
            reference = result
        elif result != reference:
            raise RuntimeError("Hasil berubah antar-pengulangan untuk konfigurasi sama.")

    if reference is None:
        raise RuntimeError("Tidak ada pengukuran yang berhasil dijalankan.")
    deviation = statistics.stdev(durations) if len(durations) > 1 else 0.0
    return statistics.median(durations), deviation, reference


def make_row(
    *,
    experiment: str,
    mode: str,
    processes: int,
    scenarios: int,
    samples_per_scenario: int,
    repeats: int,
    median_seconds: float,
    std_seconds: float,
    result: WorkloadResult,
    speedup: float | None,
    efficiency: float | None,
    baseline_seconds: float | None,
    metadata: dict[str, object],
) -> dict[str, object]:
    """Menyatukan pengukuran, metrik, hasil, dan metadata mesin."""
    return {
        "experiment": experiment,
        "mode": mode,
        "processes": processes,
        "scenarios": scenarios,
        "samples_per_scenario": samples_per_scenario,
        "total_samples": scenarios * samples_per_scenario,
        "repeats": repeats,
        "median_seconds": median_seconds,
        "std_seconds": std_seconds,
        "speedup": speedup,
        "efficiency": efficiency,
        "baseline_seconds": baseline_seconds,
        "inside_circle": result.inside_circle,
        "pi_estimate": result.pi_estimate,
        "result_consistent": True,
        **metadata,
    }


def run_benchmarks(
    process_counts: list[int],
    repeats: int,
    scenarios: int,
    samples_per_scenario: int,
    scenarios_per_process: int,
    seed: int,
) -> pd.DataFrame:
    """Menjalankan baseline serial, strong scaling, dan weak scaling."""
    metadata = device_metadata()
    rows: list[dict[str, object]] = []

    # Baseline serial menjadi pembanding strong scaling pada ukuran tetap.
    baseline_time, baseline_std, baseline_result = measure(
        lambda: run_serial(scenarios, samples_per_scenario, seed), repeats
    )
    rows.append(make_row(
        experiment="strong", mode="serial_baseline", processes=1,
        scenarios=scenarios, samples_per_scenario=samples_per_scenario,
        repeats=repeats, median_seconds=baseline_time, std_seconds=baseline_std,
        result=baseline_result, speedup=1.0, efficiency=None,
        baseline_seconds=baseline_time, metadata=metadata,
    ))

    # Strong scaling mempertahankan ukuran masalah dan memperbesar proses.
    for processes in process_counts:
        median, deviation, result = measure(
            lambda processes=processes: run_parallel(
                scenarios, samples_per_scenario, processes, seed
            ), repeats
        )
        if result != baseline_result:
            raise RuntimeError(
                f"Hasil strong scaling tidak sama dengan serial pada {processes} proses."
            )
        speedup = baseline_time / median
        rows.append(make_row(
            experiment="strong", mode="multiprocessing", processes=processes,
            scenarios=scenarios, samples_per_scenario=samples_per_scenario,
            repeats=repeats, median_seconds=median, std_seconds=deviation,
            result=result, speedup=speedup, efficiency=speedup / processes,
            baseline_seconds=baseline_time, metadata=metadata,
        ))

    # Weak scaling menjaga skenario per proses, dengan serial pembanding setara.
    for processes in process_counts:
        weak_scenarios = processes * scenarios_per_process
        serial_time, serial_std, serial_result = measure(
            lambda weak_scenarios=weak_scenarios: run_serial(
                weak_scenarios, samples_per_scenario, seed
            ), repeats
        )
        rows.append(make_row(
            experiment="weak", mode="serial_reference", processes=1,
            scenarios=weak_scenarios, samples_per_scenario=samples_per_scenario,
            repeats=repeats, median_seconds=serial_time, std_seconds=serial_std,
            result=serial_result, speedup=1.0, efficiency=None,
            baseline_seconds=serial_time, metadata=metadata,
        ))
        parallel_time, parallel_std, parallel_result = measure(
            lambda processes=processes, weak_scenarios=weak_scenarios: run_parallel(
                weak_scenarios, samples_per_scenario, processes, seed
            ), repeats
        )
        if parallel_result != serial_result:
            raise RuntimeError(
                f"Hasil weak scaling tidak sama dengan serial pada {processes} proses."
            )
        speedup = serial_time / parallel_time
        rows.append(make_row(
            experiment="weak", mode="multiprocessing", processes=processes,
            scenarios=weak_scenarios, samples_per_scenario=samples_per_scenario,
            repeats=repeats, median_seconds=parallel_time, std_seconds=parallel_std,
            result=parallel_result, speedup=speedup, efficiency=speedup / processes,
            baseline_seconds=serial_time, metadata=metadata,
        ))
    return pd.DataFrame(rows)


def parse_arguments() -> argparse.Namespace:
    """Membaca parameter benchmark dari command line."""
    parser = argparse.ArgumentParser(
        description="Benchmark Monte Carlo untuk studi strong/weak scaling."
    )
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--scenarios", type=int, default=DEFAULT_SCENARIOS)
    parser.add_argument(
        "--samples-per-scenario", type=int, default=DEFAULT_SAMPLES_PER_SCENARIO
    )
    parser.add_argument(
        "--scenarios-per-process", type=int, default=DEFAULT_SCENARIOS_PER_PROCESS
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--processes", type=int, nargs="+",
        help="Jumlah proses yang diuji; default 1, 2, 4, ... sampai core fisik.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).resolve().parents[1] / "reports",
    )
    arguments = parser.parse_args()

    if arguments.repeats < 5:
        parser.error("--repeats harus minimal 5 sesuai rancangan eksperimen.")
    if arguments.scenarios < 1 or arguments.samples_per_scenario < 1:
        parser.error("Ukuran masalah harus lebih besar dari nol.")
    if arguments.scenarios_per_process < 1:
        parser.error("--scenarios-per-process harus minimal 1.")

    physical_cores = physical_core_count()
    if arguments.processes is None:
        arguments.processes = default_process_counts(physical_cores)
    elif any(count < 1 or count > physical_cores for count in arguments.processes):
        parser.error(f"Jumlah proses harus antara 1 dan {physical_cores} core fisik.")
    elif len(set(arguments.processes)) != len(arguments.processes):
        parser.error("Jumlah proses tidak boleh duplikat.")
    return arguments


def main() -> None:
    """Menjalankan eksperimen lalu menulis CSV hasil."""
    arguments = parse_arguments()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    results = run_benchmarks(
        process_counts=arguments.processes,
        repeats=arguments.repeats,
        scenarios=arguments.scenarios,
        samples_per_scenario=arguments.samples_per_scenario,
        scenarios_per_process=arguments.scenarios_per_process,
        seed=arguments.seed,
    )
    output = arguments.output_dir / "hasil_benchmark.csv"
    results.to_csv(output, index=False)
    print(f"Hasil disimpan ke: {output}")
    print(results[[
        "experiment", "mode", "processes", "median_seconds", "std_seconds",
        "speedup", "efficiency",
    ]].to_string(index=False))


if __name__ == "__main__":
    # Guard ini diperlukan agar multiprocessing aman pada Windows.
    multiprocessing.freeze_support()
    main()



