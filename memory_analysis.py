#!/usr/bin/env python3
"""
Memory Analysis Script
Based on the requirements about /memory@0, /reserved-memory/atf@0 and CMA regions
"""

import os
import sys
import struct
import subprocess
from collections import defaultdict

class MemoryAnalyzer:
    def __init__(self):
        self.memory_layout = []

    def analyze_ram(self):
        """Analyze available RAM"""
        print("=== RAM Analysis ===")
        try:
            # Try to get memory info
            if os.path.exists('/proc/meminfo'):
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    print("Memory Info:")
                    for line in meminfo.split('\n'):
                        if line.startswith(('MemTotal:', 'MemFree:', 'MemAvailable:')):
                            print(f"  {line}")
            else:
                # Simulate memory info for demonstration
                print("Memory Info (simulated):")
                print("  MemTotal: 16477240 kB")
                print("  MemFree: 2195128 kB")
                print("  MemAvailable: ~10MB")

        except Exception as e:
            print(f"Could not read memory info: {e}")

    def analyze_reserved_memory(self):
        """Analyze reserved memory regions"""
        print("\n=== Reserved Memory Analysis ===")

        # Check if we have access to iomem (Linux)
        if os.path.exists('/proc/iomem'):
            try:
                with open('/proc/iomem', 'r') as f:
                    iomem = f.read()
                    print("Reserved Memory Regions:")
                    for line in iomem.split('\n'):
                        if 'reserved' in line.lower():
                            print(f"  {line}")
            except Exception as e:
                print(f"Error reading /proc/iomem: {e}")
        else:
            print("Reserved Memory Regions (simulated):")
            print("  /memory@0")
            print("  /reserved-memory/atf@0")
            print("  (These would appear in a real system with device tree)")

    def analyze_cma_regions(self):
        """Analyze CMA (Contiguous Memory Allocator) regions"""
        print("\n=== CMA Regions Analysis ===")

        if os.path.exists('/proc/cma'):
            try:
                with open('/proc/cma', 'r') as f:
                    cma_info = f.read()
                    print("CMA Information:")
                    print(cma_info)
            except Exception as e:
                print(f"Error reading CMA info: {e}")
        else:
            print("CMA Regions (simulated):")
            print("  linux,cma - Contiguous Memory Allocator")
            print("  (Would typically appear in /proc/iomem or device tree)")

    def simulate_memory_test(self):
        """Simulate memory testing"""
        print("\n=== Memory Test Simulation ===")

        # Test 1: Basic RAM allocation
        try:
            # Allocate 1MB of memory
            test_data = bytearray(1024 * 1024)
            print(f"✓ Allocated 1MB of memory")

            # Fill with pattern
            for i in range(len(test_data)):
                test_data[i] = i % 256

            # Verify
            for i in range(0, len(test_data), 1024):  # Check every 1KB block
                if test_data[i] != i % 256:
                    print("✗ Memory corruption detected")
                    return False

            print("✓ Memory test passed")

        except Exception as e:
            print(f"✗ Memory test failed: {e}")
            return False

        return True

    def run_all_tests(self):
        """Run all memory analysis tests"""
        print("Memory Analysis and Testing Suite")
        print("=================================")

        try:
            self.analyze_ram()
            self.analyze_reserved_memory()
            self.analyze_cma_regions()
            success = self.simulate_memory_test()

            if success:
                print("\n✓ All memory tests completed successfully")
            else:
                print("\n✗ Some memory tests failed")

            return success

        except Exception as e:
            print(f"Error running tests: {e}")
            return False

def main():
    analyzer = MemoryAnalyzer()
    return 0 if analyzer.run_all_tests() else 1

if __name__ == "__main__":
    sys.exit(main())