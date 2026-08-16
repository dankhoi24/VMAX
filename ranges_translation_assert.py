#!/usr/bin/env python3
"""
Ranges Translation Test with Assertions
Testing bus_address, cpu_address, size, translation_path
for a simple serial device.
"""

import unittest
from typing import Dict, List

class RangeTranslation:
    """Handle translation of memory ranges for devices"""

    def __init__(self):
        self.ranges = []

    def add_range(self, bus_address: int, cpu_address: int, size: int, translation_path: str = ""):
        """Add a translation range"""
        self.ranges.append({
            'bus_address': bus_address,
            'cpu_address': cpu_address,
            'size': size,
            'translation_path': translation_path
        })

    def translate(self, bus_address: int) -> Dict:
        """Translate a bus address to cpu address"""
        for range_info in self.ranges:
            # Check if bus_address falls within this range
            if (bus_address >= range_info['bus_address'] and
                bus_address < range_info['bus_address'] + range_info['size']):

                # Calculate offset within the range
                offset = bus_address - range_info['bus_address']
                # Translate to CPU address
                cpu_address = range_info['cpu_address'] + offset

                return {
                    'cpu_address': cpu_address,
                    'size': range_info['size'],
                    'translation_path': range_info['translation_path']
                }
        return None

class TestRangesTranslationAssert(unittest.TestCase):
    """Test cases with assertions for ranges translation"""

    def setUp(self):
        self.translator = RangeTranslation()

    def test_serial_device_translation(self):
        """Test serial device ranges translation"""
        # Add serial device range: bus 0x1000 -> cpu 0x4000, size 0x1000
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

        # Test translation - this will be our assertion
        result = self.translator.translate(0x1000)
        self.assertIsNotNone(result)

        # Assert bus_address
        self.assertEqual(result['cpu_address'], 0x4000)
        self.assertEqual(result['size'], 0x1000)
        self.assertEqual(result['translation_path'], "serial0")

        # Test with middle address
        result = self.translator.translate(0x1500)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x4500)
        self.assertEqual(result['size'], 0x1000)
        self.assertEqual(result['translation_path'], "serial0")

        # Test boundary condition
        result = self.translator.translate(0x1FFF)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x5FFF)
        self.assertEqual(result['size'], 0x1000)
        self.assertEqual(result['translation_path'], "serial0")

    def test_range_boundaries(self):
        """Test range boundary conditions with assertions"""
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

        # Test exact start address
        result = self.translator.translate(0x1000)
        self.assertEqual(result['cpu_address'], 0x4000)

        # Test exact end address (should not be included - exclusive)
        result = self.translator.translate(0x1FFF)
        self.assertEqual(result['cpu_address'], 0x5FFF)

        # Test address just past range (should not translate)
        result = self.translator.translate(0x2000)
        self.assertIsNone(result)

        # Test address before range (should not translate)
        result = self.translator.translate(0x0FFF)
        self.assertIsNone(result)

    def test_multiple_devices(self):
        """Test multiple device ranges"""
        # Add first serial device
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")
        # Add second serial device
        self.translator.add_range(0x2000, 0x5000, 0x1000, "serial1")

        # Test first device
        result = self.translator.translate(0x1500)
        self.assertEqual(result['cpu_address'], 0x4500)
        self.assertEqual(result['translation_path'], "serial0")

        # Test second device
        result = self.translator.translate(0x2500)
        self.assertEqual(result['cpu_address'], 0x5500)
        self.assertEqual(result['translation_path'], "serial1")

def run_assertion_tests():
    """Run tests with assertions"""
    print("Running Ranges Translation Tests with Assertions...")

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRangesTranslationAssert)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()

def main():
    """Main function demonstrating ranges translation with assertions"""
    print("Ranges Translation Test with Assertions")
    print("========================================")

    # Test with a simple serial device
    print("\nTesting with simple serial device:")

    # Create translator instance
    translator = RangeTranslation()

    # Add serial device range
    # bus_address: 0x1000, cpu_address: 0x4000, size: 0x1000, translation_path: "serial0"
    translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

    # Test different addresses
    test_cases = [
        (0x1000, 0x4000, "serial0"),  # Start of range
        (0x1500, 0x4500, "serial0"),  # Middle of range
        (0x1FFF, 0x5FFF, "serial0"),  # End of range
    ]

    print("\nAddress Translation Test:")
    print("Bus Address  | CPU Address  | Translation Path")
    print("-" * 45)

    for bus_addr, expected_cpu, expected_path in test_cases:
        result = translator.translate(bus_addr)
        if result:
            print(f"0x{bus_addr:04X}      | 0x{result['cpu_address']:04X}      | {result['translation_path']}")
        else:
            print(f"0x{bus_addr:04X}      | None         | Not in range")

    # Run assertion tests
    print("\n" + "="*50)
    print("Running Assertion Tests...")

    success = run_assertion_tests()

    if success:
        print("\n✓ All assertion tests passed!")
        print("\nSummary:")
        print("- bus_address: 0x1000 (start of serial device range)")
        print("- cpu_address: 0x4000 (mapped CPU address)")
        print("- size: 0x1000 (1KB range)")
        print("- translation_path: 'serial0' (device identifier)")
    else:
        print("\n✗ Some assertion tests failed!")

    return success

if __name__ == "__main__":
    main()