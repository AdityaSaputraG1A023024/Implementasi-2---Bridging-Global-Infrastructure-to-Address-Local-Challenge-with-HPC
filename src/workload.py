"""Beban kerja Monte Carlo untuk menghitung pendekatan nilai pi."""

from __future__ import annotations

import multiprocessing
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadResult:
    """Ringkasan hitungan titik Monte Carlo."""

    inside_circle: int
    total_points: int

    @property
    def pi_estimate(self) -> float:
        """Mengubah proporsi titik di lingkaran menjadi estimasi pi."""
        return 4.0 * self.inside_circle / self.total_points


def _simulate_scenario(arguments: tuple[int, int, int]) -> int:
    """Menghitung titik dalam lingkaran untuk satu skenario ber-seed tetap."""
    scenario_id, samples_per_scenario, seed = arguments
    generator = random.Random(seed + scenario_id)
    inside_circle = 0

    for _ in range(samples_per_scenario):
        x = generator.uniform(-1.0, 1.0)
        y = generator.uniform(-1.0, 1.0)
        if x * x + y * y <= 1.0:
            inside_circle += 1

    return inside_circle


def _validate_workload(scenarios: int, samples_per_scenario: int) -> None:
    """Memastikan ukuran masalah masuk akal sebelum memulai komputasi."""
    if scenarios < 1:
        raise ValueError("Jumlah skenario harus minimal 1.")
    if samples_per_scenario < 1:
        raise ValueError("Jumlah sampel per skenario harus minimal 1.")


def run_serial(
    scenarios: int,
    samples_per_scenario: int,
    seed: int = 20261020,
) -> WorkloadResult:
    """Menjalankan seluruh skenario berurutan sebagai baseline serial."""
    _validate_workload(scenarios, samples_per_scenario)
    tasks = (
        (scenario_id, samples_per_scenario, seed)
        for scenario_id in range(scenarios)
    )
    inside_circle = sum(_simulate_scenario(task) for task in tasks)
    return WorkloadResult(
        inside_circle=inside_circle,
        total_points=scenarios * samples_per_scenario,
    )


def run_parallel(
    scenarios: int,
    samples_per_scenario: int,
    processes: int,
    seed: int = 20261020,
) -> WorkloadResult:
    """Membagikan skenario independen ke proses pekerja."""
    _validate_workload(scenarios, samples_per_scenario)
    if processes < 1:
        raise ValueError("Jumlah proses harus minimal 1.")

    tasks = [
        (scenario_id, samples_per_scenario, seed)
        for scenario_id in range(scenarios)
    ]
    chunk_size = max(1, scenarios // (processes * 4))

    # Seed mengikuti ID skenario, bukan urutan proses, sehingga hasil konsisten.
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=processes) as pool:
        counts = pool.map(_simulate_scenario, tasks, chunksize=chunk_size)

    return WorkloadResult(
        inside_circle=sum(counts),
        total_points=scenarios * samples_per_scenario,
    )
