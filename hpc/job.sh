#!/bin/bash
# TEMPLATE SLURM: belum diuji karena lingkungan lokal tidak memiliki akses HPC.
# SBATCH menentukan nama pekerjaan, node, task, CPU, batas waktu, dan log.
#SBATCH --job-name=benchmark-paralel
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:20:00
#SBATCH --output=benchmark-%j.out

# Hentikan skrip jika ada perintah gagal atau variabel belum ditentukan.
set -euo pipefail

# Muat Python yang disediakan administrator cluster; sesuaikan nama modul.
module load python/3.11

# Aktifkan lingkungan virtual yang telah dipasang pada cluster.
source .venv/bin/activate

# Gunakan direktori tempat pekerjaan SLURM dikirim.
cd "${SLURM_SUBMIT_DIR}"

# Jalankan multiprocess lokal sesuai CPU yang diminta dari SLURM.
python src/benchmark.py --processes 1 2 4 8 --repeats 5

# Buat grafik dari CSV yang dihasilkan oleh benchmark.
python src/plot_results.py
