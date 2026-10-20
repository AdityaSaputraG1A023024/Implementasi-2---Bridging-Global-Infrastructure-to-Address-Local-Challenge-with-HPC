"""Uji konsistensi hasil serial dan multiprocessing."""

import unittest

from src.workload import run_parallel, run_serial


class WorkloadTests(unittest.TestCase):
    """Memastikan seed dan pembagian skenario tidak mengubah hasil."""

    def test_serial_and_parallel_results_match(self) -> None:
        serial = run_serial(scenarios=8, samples_per_scenario=2_000, seed=77)
        for processes in (1, 2, 4):
            with self.subTest(processes=processes):
                parallel = run_parallel(
                    scenarios=8,
                    samples_per_scenario=2_000,
                    processes=processes,
                    seed=77,
                )
                self.assertEqual(parallel, serial)

    def test_invalid_workload_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_serial(scenarios=0, samples_per_scenario=10)
        with self.assertRaises(ValueError):
            run_parallel(scenarios=1, samples_per_scenario=10, processes=0)


if __name__ == "__main__":
    unittest.main()
