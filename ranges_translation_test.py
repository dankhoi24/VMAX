#!/usr/bin/env python3
"""
Ranges Translation Test
Testing translation of bus_address, cpu_address, size, and translation_path
for a simple device like serial communication.
"""

import unittest
from typing import Dict, List, Optional

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

    def translate(self, bus_address: int) -> Optional[Dict]:
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

    def get_range_info(self, bus_address: int) -> Optional[Dict]:
        """Get detailed range information"""
        for range_info in self.ranges:
            if (bus_address >= range_info['bus_address'] and
                bus_address < range_info['bus_address'] + range_info['size']):
                return range_info
        return None

class TestRangesTranslation(unittest.TestCase):
    """Test cases for ranges translation"""

    def setUp(self):
        self.translator = RangeTranslation()

    def test_simple_translation(self):
        """Test basic translation functionality"""
        # Add a simple range: bus 0x1000 -> cpu 0x4000, size 0x1000
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

        # Test translation
        result = self.translator.translate(0x1500)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x4500)  # 0x4000 + (0x1500 - 0x1000)
        self.assertEqual(result['size'], 0x1000)
        self.assertEqual(result['translation_path'], "serial0")

    def test_range_boundary(self):
        """Test range boundary conditions"""
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

        # Test exact boundary
        result = self.translator.translate(0x1000)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x4000)

        # Test one byte past boundary
        result = self.translator.translate(0x2000)
        self.assertIsNone(result)  # Should be outside range

    def test_multiple_ranges(self):
        """Test multiple ranges"""
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")
        self.translator.add_range(0x2000, 0x5000, 0x1000, "serial1")

        # Test first range
        result = self.translator.translate(0x1500)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x4500)

        # Test second range
        result = self.translator.translate(0x2500)
        self.assertIsNotNone(result)
        self.assertEqual(result['cpu_address'], 0x5500)

    def test_range_info_lookup(self):
        """Test getting range information"""
        self.translator.add_range(0x1000, 0x4000, 0x1000, "serial0")

        info = self.translator.get_range_info(0x1500)
        self.assertIsNotNone(info)
        self.assertEqual(info['bus_address'], 0x1000)
        self.assertEqual(info['cpu_address'], 0x4000)
        self.assertEqual(info['size'], 0x1000)
        self.assertEqual(info['translation_path'], "serial0")

def run_tests():
    """Run all tests"""
    print("Running Ranges Translation Tests...")

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRangesTranslation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✓ All tests passed!")
        return True
    else:
        print(f"\n✗ {len(result.failures)} failures, {len(result.errors)} errors")
        return False

def main():
    """Main function demonstrating ranges translation"""
    print("Ranges Translation Test")
    print("======================")

    # Create translator instance
    translator = RangeTranslation()

    # Add serial device ranges
    print("Adding serial device ranges:")
    translator.add_range(0x1000, 0x4000, 0x1000, "serial0")
    translator.add_range(0x2000, 0x5000, 0x1000, "serial1")

    # Test translations
    test_addresses = [0x1000, 0x1500, 0x1FFF, 0x2000, 0x2500, 0x2FFF]

    print("\nTranslation Results:")
    print("Bus Address  | CPU Address  | Range Info")
    print("-" * 40)

    for addr in test_addresses:
        translation = translator.translate(addr)
        if translation:
            print(f"0x{addr:04X}      | 0x{translation['cpu_address']:04X}      | {translation['translation_path']}")
        else:
            print(f"0x{addr:04X}      | -            | Out of range")

    # Run unit tests
    print("\n" + "="*50)
    success = run_tests()

    if success:
        print("\n✓ Ranges translation test completed successfully")
    else:
        print("\n✗ Ranges translation test failed")

    return success

if __name__ == "__main__":
    main()