"""Membuat grafik benchmark dari CSV hasil yang sudah dihasilkan."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def create_figures(csv_path: Path, output_dir: Path) -> None:
    """Menyimpan grafik waktu, speedup ideal, dan efisiensi."""
    results = pd.read_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    strong = results[results["experiment"] == "strong"]
    strong_parallel = strong[strong["mode"] == "multiprocessing"].sort_values(
        "processes"
    )
    weak_parallel = results[
        (results["experiment"] == "weak")
        & (results["mode"] == "multiprocessing")
    ].sort_values("processes")

    # Grafik waktu menampilkan strong scaling dan weak scaling.
    figure, axis = plt.subplots(figsize=(8, 5))
    strong_baseline = strong[strong["mode"] == "serial_baseline"]
    axis.axhline(
        strong_baseline.iloc[0]["median_seconds"], color="gray", linestyle=":",
        label="Baseline serial strong",
    )
    axis.plot(strong_parallel["processes"], strong_parallel["median_seconds"],
              marker="o", label="Strong scaling")
    axis.plot(weak_parallel["processes"], weak_parallel["median_seconds"],
              marker="s", label="Weak scaling")
    axis.set_xticks(sorted(set(strong_parallel["processes"]).union(
        weak_parallel["processes"]
    )))
    axis.set(xlabel="Jumlah proses", ylabel="Waktu median (detik)",
             title="Waktu eksekusi benchmark")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "waktu_eksekusi.png", dpi=150)
    plt.close(figure)

    # Speedup ideal strong scaling menjadi garis pembanding linear.
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(strong_parallel["processes"], strong_parallel["speedup"],
              marker="o", label="Speedup terukur")
    axis.plot(strong_parallel["processes"], strong_parallel["processes"],
              linestyle="--", label="Speedup ideal")
    axis.set_xticks(strong_parallel["processes"])
    axis.set(xlabel="Jumlah proses", ylabel="Speedup",
             title="Speedup strong scaling")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "speedup.png", dpi=150)
    plt.close(figure)

    # Efisiensi dibandingkan antarproses untuk strong dan weak scaling.
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(strong_parallel["processes"], strong_parallel["efficiency"],
              marker="o", label="Strong scaling")
    axis.plot(weak_parallel["processes"], weak_parallel["efficiency"],
              marker="s", label="Weak scaling")
    axis.axhline(1.0, color="gray", linestyle=":", label="Efisiensi ideal")
    axis.set_xticks(sorted(set(strong_parallel["processes"]).union(
        weak_parallel["processes"]
    )))
    axis.set(xlabel="Jumlah proses", ylabel="Efisiensi",
             title="Efisiensi terhadap jumlah proses")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "efisiensi.png", dpi=150)
    plt.close(figure)
    print(f"Grafik disimpan di: {output_dir}")


def main() -> None:
    """Membaca lokasi CSV dan folder tujuan grafik."""
    parser = argparse.ArgumentParser(description="Plot hasil benchmark CSV.")
    default_reports = Path(__file__).resolve().parents[1] / "reports"
    parser.add_argument("--csv", type=Path,
                        default=default_reports / "hasil_benchmark.csv")
    parser.add_argument("--output-dir", type=Path,
                        default=default_reports / "figures")
    arguments = parser.parse_args()
    create_figures(arguments.csv, arguments.output_dir)


if __name__ == "__main__":
    main()
