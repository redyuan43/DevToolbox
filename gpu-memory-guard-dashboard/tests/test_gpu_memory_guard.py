#!/usr/bin/env python3
import importlib.util
import sys
import textwrap
import unittest


SPEC = importlib.util.spec_from_file_location("gpu_memory_guard", "daemon/gpu-memory-guard.py")
guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)


class GpuMemoryGuardTests(unittest.TestCase):
    def test_parse_nvidia_smi_processes(self):
        output = textwrap.dedent(
            """
            +-----------------------------------------------------------------------------------------+
            | Processes:                                                                              |
            |  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
            |=========================================================================================|
            |    0   N/A  N/A           11387      G   /usr/lib/xorg/Xorg                      150MiB |
            |    0   N/A  N/A           14035      G   ....mount_lmstudm2nZOA/lm-studio         86MiB |
            +-----------------------------------------------------------------------------------------+
            """
        )
        processes = guard.parse_nvidia_smi_processes(output)
        self.assertEqual([(p.pid, p.name, p.used_mib, p.source) for p in processes], [
            (11387, "Xorg", 150, "nvidia-smi"),
            (14035, "lm-studio", 86, "nvidia-smi"),
        ])

    def test_parse_amd_smi_processes_flexible_json(self):
        output = """
        [
          {
            "gpu": 0,
            "process_list": [
              {
                "pid": 1234,
                "process_name": "python",
                "memory_usage": "24576 MiB"
              }
            ]
          }
        ]
        """
        processes = guard.parse_amd_smi_processes(output)
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].pid, 1234)
        self.assertEqual(processes[0].name, "python")
        self.assertEqual(processes[0].used_mib, 24576)
        self.assertEqual(processes[0].source, "amd-smi")

    def test_parse_nvidia_gpu_memory(self):
        output = """
        0, NVIDIA GeForce RTX 3060, 12288, 11060
        1, NVIDIA GeForce RTX 3060, 12288, 23
        0, NVIDIA GB10, [N/A], [N/A]
        """
        devices = guard.parse_nvidia_gpu_memory(output)
        self.assertEqual([(d.label, d.used_mib, d.total_mib) for d in devices], [
            ("nvidia:0:NVIDIA GeForce RTX 3060", 11060, 12288),
            ("nvidia:1:NVIDIA GeForce RTX 3060", 23, 12288),
        ])

    def test_parse_rocm_smi_memory(self):
        output = """
        {
          "card0": {
            "VRAM Total Used Memory (B)": "2503127040",
            "GTT Total Used Memory (B)": "248041472"
          }
        }
        """
        self.assertEqual(guard.parse_rocm_smi_memory_mib(output), 2623)

    def test_choose_victim_skips_protected_and_picks_largest(self):
        protected = {"Xorg"}
        processes = [
            guard.GpuProcess(pid=1, name="Xorg", used_mib=50000, source="test"),
            guard.GpuProcess(pid=2, name="python", used_mib=40000, source="test"),
            guard.GpuProcess(pid=3, name="ollama", used_mib=30000, source="test"),
        ]
        victim = guard.choose_victim(processes, protected)
        self.assertIsNotNone(victim)
        self.assertEqual(victim.pid, 2)

    def test_should_trigger_on_unified_memory_pressure(self):
        sample = guard.Sample(
            meminfo=guard.MemInfo(total_mib=1000, available_mib=90),
            processes=[guard.GpuProcess(pid=2, name="python", used_mib=100, source="test")],
            gpu_used_mib=100,
            devices=[],
            details=[],
        )
        trigger, reason = guard.should_trigger(sample, 900)
        self.assertTrue(trigger)
        self.assertIn("mem_used", reason)

    def test_should_trigger_on_dedicated_gpu_memory_pressure(self):
        sample = guard.Sample(
            meminfo=guard.MemInfo(total_mib=48000, available_mib=30000),
            processes=[guard.GpuProcess(pid=2, name="python", used_mib=11060, source="test")],
            gpu_used_mib=11060,
            devices=[guard.GpuDeviceMemory(label="nvidia:0:RTX 3060", used_mib=11060, total_mib=12288, source="test")],
            details=[],
        )
        trigger, reason = guard.should_trigger(sample, 43200, threshold_percent=90)
        self.assertTrue(trigger)
        self.assertIn("nvidia:0:RTX 3060", reason)


if __name__ == "__main__":
    unittest.main()
