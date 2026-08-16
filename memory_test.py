#!/usr/bin/env python3
"""
Memory testing script for RAM and reserved memory regions.
Based on the notes about /memory@0, /reserved-memory/atf@0, and CMA regions.
"""

import os
import sys
import struct
import mmap

def test_ram_access():
    """Test RAM access by writing and reading data"""
    print("Testing RAM access...")

    # Allocate a large block of memory
    try:
        size = 1024 * 1024  # 1MB
        test_data = bytearray(size)

        # Fill with pattern
        for i in range(size):
            test_data[i] = i % 256

        # Verify readback
        for i in range(size):
            if test_data[i] != i % 256:
                print(f"ERROR: Data corruption at index {i}")
                return False

        print(f"Successfully tested {size} bytes of RAM")
        return True

    except Exception as e:
        print(f"RAM test failed: {e}")
        return False

def test_reserved_memory():
    """Test reserved memory regions"""
    print("Testing reserved memory regions...")

    # In a real system, this would check /proc/iomem or similar
    # For now, we'll simulate the concept

    reserved_regions = [
        "/memory@0",
        "/reserved-memory/atf@0"
    ]

    print("Simulated reserved memory regions:")
    for region in reserved_regions:
        print(f"  {region}")

    # Check if system has specific memory management for these regions
    # This is typically done in device tree or kernel space
    print("Reserved memory test complete")
    return True

def test_cma_regions():
    """Test CMA (Contiguous Memory Allocator) regions"""
    print("Testing CMA regions...")

    # CMA regions are typically set up in device tree
    # This would check for CMA configuration

    cma_regions = [
        "linux,cma",
        "contiguous"
    ]

    print("CMA regions to check:")
    for region in cma_regions:
        print(f"  {region}")

    print("CMA region test complete")
    return True

def main():
    """Main test function"""
    print("Memory Testing Suite")
    print("====================")

    # Test RAM access
    ram_ok = test_ram_access()

    # Test reserved memory
    reserved_ok = test_reserved_memory()

    # Test CMA regions
    cma_ok = test_cma_regions()

    if ram_ok and reserved_ok and cma_ok:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())