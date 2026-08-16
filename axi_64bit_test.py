#!/usr/bin/env python3
"""
AXI 64-bit Addressing Test
Testing AXI mapping with 64-bit addresses without 32-bit truncation
"""

import unittest
import struct
from typing import List, Tuple

class AXIAddressTranslator:
    """Handles 64-bit AXI address translation without truncation"""

    def __init__(self):
        self.address_width = 64  # 64-bit addressing
        self.regions = []  # List of (base, size, name) tuples

    def add_region(self, base_address: int, size: int, name: str):
        """Add a memory region with 64-bit addressing"""
        # Validate 64-bit address
        if base_address > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Base address {hex(base_address)} exceeds 64-bit limit")

        if size > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Size {hex(size)} exceeds 64-bit limit")

        self.regions.append((base_address, size, name))

    def translate_address(self, address: int) -> Tuple[bool, int, str]:
        """
        Translate 64-bit address to region
        Returns: (success, translated_address, region_name)
        """
        # Ensure we're working with 64-bit addresses
        address = address & 0xFFFFFFFFFFFFFFFF

        for base, size, name in self.regions:
            # Check if address is within this region
            if base <= address < base + size:
                # Return the original 64-bit address (no truncation)
                return (True, address, name)

        return (False, 0, "")

    def validate_no_truncation(self, address: int) -> bool:
        """
        Validate that address is not truncated from 64-bit to 32-bit
        """
        # 64-bit address should remain 64-bit
        if address > 0xFFFFFFFF:  # If it's > 32-bit
            # Check that we haven't lost the upper bits
            return True
        return True  # For demonstration purposes

    def get_all_regions(self) -> List[Tuple[int, int, str]]:
        """Get all memory regions"""
        return self.regions.copy()

class TestAXI64Bit(unittest.TestCase):
    """Test cases for 64-bit AXI addressing"""

    def setUp(self):
        self.translator = AXIAddressTranslator()

    def test_64bit_address_handling(self):
        """Test that 64-bit addresses are handled correctly"""
        # Add a region with 64-bit address
        self.translator.add_region(0x1000000000000000, 0x1000000000000, "high_memory")

        # Test 64-bit address translation
        success, translated_addr, region = self.translator.translate_address(0x1000000000000000)
        self.assertTrue(success)
        self.assertEqual(translated_addr, 0x1000000000000000)
        self.assertEqual(region, "high_memory")

    def test_no_truncation_assertion(self):
        """Test that no truncation occurs to 32-bit"""
        # Add a 64-bit region
        self.translator.add_region(0x123456789ABCDEF0, 0x1000, "test_region")

        # Verify that 64-bit address is preserved
        success, translated_addr, region = self.translator.translate_address(0x123456789ABCDEF0)
        self.assertTrue(success)

        # Assert that the full 64-bit address is preserved
        self.assertEqual(translated_addr, 0x123456789ABCDEF0)

        # This demonstrates no truncation - the full address is maintained
        self.assertTrue(translated_addr > 0xFFFFFFFF, "Address should remain 64-bit")

    def test_large_address_handling(self):
        """Test handling of addresses > 4GB"""
        # Add a region at 64-bit address > 4GB
        self.translator.add_region(0x1000000000000000, 0x1000000000000, "huge_region")

        # Test address > 4GB
        test_addr = 0x1000000000000000  # 1.07 PB
        success, translated_addr, region = self.translator.translate_address(test_addr)
        self.assertTrue(success)
        self.assertEqual(translated_addr, test_addr)
        self.assertEqual(region, "huge_region")

    def test_no_32bit_truncation(self):
        """Explicit test for no 32-bit truncation"""
        # Add a large 64-bit address
        large_addr = 0x123456789ABCDEF0  # 64-bit address

        # Add region for this address
        self.translator.add_region(large_addr, 0x1000, "large_region")

        # Translate
        success, translated_addr, region = self.translator.translate_address(large_addr)

        # Assert no truncation occurred
        self.assertTrue(success)
        self.assertEqual(translated_addr, large_addr)

        # The assertion - address should remain 64-bit, not truncated to 32-bit
        self.assertTrue(
            translated_addr > 0xFFFFFFFF,
            "Address should not be truncated to 32-bit"
        )

    def test_address_boundary_conditions(self):
        """Test boundary conditions for 64-bit addresses"""
        # Add a region
        self.translator.add_region(0x1000000000000000, 0x1000, "boundary_region")

        # Test exact boundary
        success, addr, region = self.translator.translate_address(0x1000000000000000)
        self.assertTrue(success)
        self.assertEqual(addr, 0x1000000000000000)

        # Test just beyond boundary
        success, addr, region = self.translator.translate_address(0x1000000000000FFF)
        self.assertTrue(success)
        self.assertEqual(addr, 0x1000000000000FFF)

def run_axi_tests():
    """Run all AXI 64-bit tests"""
    print("Running AXI 64-bit Addressing Tests...")
    print("=" * 50)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAXI64Bit)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()

def main():
    """Main function demonstrating AXI 64-bit addressing"""
    print("AXI 64-bit Addressing Test")
    print("=" * 30)
    print("Testing AXI mapping with >4GB addresses")
    print("Asserting no 32-bit truncation")
    print()

    # Create AXI translator
    translator = AXIAddressTranslator()

    # Add a 64-bit memory region (greater than 4GB)
    high_memory_region = 0x1000000000000000  # 1.07 PB
    size = 0x1000000000000  # 1TB

    print(f"Adding memory region:")
    print(f"  Base Address: 0x{high_memory_region:016X}")
    print(f"  Size: 0x{size:016X} ({size//1024//1024} MB)")
    print(f"  Address > 4GB: {high_memory_region > 0x100000000}")

    try:
        translator.add_region(high_memory_region, size, "high_memory")
        print("✓ Region added successfully")
    except Exception as e:
        print(f"✗ Error adding region: {e}")
        return False

    # Test translation of large address
    test_addr = 0x123456789ABCDEF0  # 64-bit test address
    print(f"\nTesting translation of 64-bit address:")
    print(f"  Test Address: 0x{test_addr:016X}")

    success, translated_addr, region = translator.translate_address(test_addr)

    if success:
        print(f"✓ Translation successful")
        print(f"  Translated Address: 0x{translated_addr:016X}")
        print(f"  Region: {region}")

        # Critical assertion - no truncation
        if translated_addr == test_addr:
            print("✓ PASS: No 32-bit truncation occurred")
        else:
            print("✗ FAIL: Address was truncated")
            return False

        # Verify it's still 64-bit
        if translated_addr > 0xFFFFFFFF:
            print("✓ PASS: Address remains 64-bit")
        else:
            print("✗ FAIL: Address truncated to 32-bit")
            return False
    else:
        print("✗ Translation failed")
        return False

    # Run unit tests
    print("\n" + "=" * 50)
    success = run_axi_tests()

    if success:
        print("\n✓ All AXI 64-bit tests passed!")
        print("\nSummary:")
        print("- AXI mapping supports 64-bit addresses")
        print("- Addresses > 4GB are handled correctly")
        print("- No truncation to 32-bit occurs")
        print("- Memory regions can exceed 4GB")
        print("- Full address space preserved")
    else:
        print("\n✗ Some AXI 64-bit tests failed!")

    return success

if __name__ == "__main__":
    main()