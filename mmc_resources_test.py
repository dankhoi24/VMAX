#!/usr/bin/env python3
"""
MMC Resources Test
Testing multiple reg resources for MMC nodes with distinct resources assertion
"""

import unittest
from typing import List, Dict, Any

class MMCResource:
    """Represents a single MMC resource"""

    def __init__(self, name: str, address: int, size: int, type: str = "memory"):
        self.name = name
        self.address = address
        self.size = size
        self.type = type

    def __repr__(self):
        return f"MMCResource(name='{self.name}', address=0x{self.address:x}, size=0x{self.size:x}, type='{self.type}')"

class MMCNode:
    """Represents an MMC node with multiple resources"""

    def __init__(self, node_name: str):
        self.node_name = node_name
        self.resources: List[MMCResource] = []

    def add_resource(self, resource: MMCResource):
        """Add a resource to the MMC node"""
        self.resources.append(resource)

    def get_resources(self) -> List[MMCResource]:
        """Get all resources for this node"""
        return self.resources

    def get_resource_by_name(self, name: str) -> MMCResource:
        """Get a specific resource by name"""
        for resource in self.resources:
            if resource.name == name:
                return resource
        return None

    def validate_resources(self) -> bool:
        """Validate that all resources are distinct and properly configured"""
        # Check for duplicate addresses
        addresses = [r.address for r in self.resources]
        if len(addresses) != len(set(addresses)):
            return False

        # Check for overlapping resources
        for i, r1 in enumerate(self.resources):
            for j, r2 in enumerate(self.resources):
                if i != j:
                    # Check for overlap
                    if (r1.address < r2.address + r2.size and
                        r2.address < r1.address + r1.size):
                        return False

        return True

class TestMMCResources(unittest.TestCase):
    """Test cases for MMC resources with multiple reg assertion"""

    def setUp(self):
        self.mmc_node = MMCNode("mmc0")

    def test_single_resource(self):
        """Test single resource case"""
        resource = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource)

        resources = self.mmc_node.get_resources()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].name, "mmio")
        self.assertEqual(resources[0].address, 0x1000)
        self.assertEqual(resources[0].size, 0x1000)

    def test_multiple_distinct_resources(self):
        """Test multiple distinct resources as required"""
        # Add first resource
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add second distinct resource
        resource2 = MMCResource("dma", 0x2000, 0x800, "dma")
        self.mmc_node.add_resource(resource2)

        # Verify both resources exist
        resources = self.mmc_node.get_resources()
        self.assertEqual(len(resources), 2)

        # Verify resource 1
        self.assertEqual(resources[0].name, "mmio")
        self.assertEqual(resources[0].address, 0x1000)
        self.assertEqual(resources[0].size, 0x1000)
        self.assertEqual(resources[0].type, "memory")

        # Verify resource 2
        self.assertEqual(resources[1].name, "dma")
        self.assertEqual(resources[1].address, 0x2000)
        self.assertEqual(resources[1].size, 0x800)
        self.assertEqual(resources[1].type, "dma")

    def test_resource_distinctness_assertion(self):
        """Assert that resources are distinct as required"""
        # Add first resource
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add second distinct resource
        resource2 = MMCResource("dma", 0x2000, 0x800, "dma")
        self.mmc_node.add_resource(resource2)

        # Verify they are distinct resources
        resources = self.mmc_node.get_resources()
        self.assertEqual(len(resources), 2)

        # Assert distinct addresses
        self.assertNotEqual(resources[0].address, resources[1].address)

        # Assert distinct names
        self.assertNotEqual(resources[0].name, resources[1].name)

        # Assert distinct types
        self.assertNotEqual(resources[0].type, resources[1].type)

        # Assert they don't overlap
        self.assertTrue(resources[0].address + resources[0].size <= resources[1].address or
                       resources[1].address + resources[1].size <= resources[0].address)

    def test_overlapping_resources_assertion(self):
        """Test that overlapping resources are detected"""
        # Add first resource
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add overlapping resource (should fail validation)
        resource2 = MMCResource("dma", 0x1500, 0x800, "dma")  # Overlaps with resource1
        self.mmc_node.add_resource(resource2)

        # Validate resources (should return False due to overlap)
        self.assertFalse(self.mmc_node.validate_resources())

    def test_valid_non_overlapping_resources(self):
        """Test valid non-overlapping resources"""
        # Add first resource
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add second non-overlapping resource
        resource2 = MMCResource("dma", 0x3000, 0x800, "dma")  # Doesn't overlap
        self.mmc_node.add_resource(resource2)

        # Validate resources (should return True)
        self.assertTrue(self.mmc_node.validate_resources())

    def test_empty_node(self):
        """Test empty MMC node"""
        resources = self.mmc_node.get_resources()
        self.assertEqual(len(resources), 0)

def run_mmc_tests():
    """Run all MMC resource tests"""
    print("Running MMC Resources Tests...")
    print("=" * 40)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMMCResources)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()

def main():
    """Main function demonstrating MMC resource handling"""
    print("MMC Resources Test")
    print("=" * 30)

    # Create MMC node
    mmc_node = MMCNode("mmc0")

    # Add multiple resources - this represents the "multiple reg" requirement
    print("Adding MMC resources:")

    # First resource (memory mapped I/O)
    mmio_resource = MMCResource("mmio", 0x1000, 0x1000, "memory")
    mmc_node.add_resource(mmio_resource)
    print(f"  Added: {mmio_resource}")

    # Second resource (DMA or command registers)
    dma_resource = MMCResource("dma", 0x2000, 0x800, "dma")
    mmc_node.add_resource(dma_resource)
    print(f"  Added: {dma_resource}")

    # Validate resources
    is_valid = mmc_node.validate_resources()
    print(f"\nResource validation: {'PASS' if is_valid else 'FAIL'}")

    # Display all resources
    print("\nAll Resources:")
    for i, resource in enumerate(mmc_node.get_resources()):
        print(f"  {i+1}. {resource}")

    # Run unit tests
    print("\n" + "=" * 40)
    success = run_mmc_tests()

    if success:
        print("\n✓ All MMC resource tests passed!")
        print("\nSummary of implementation:")
        print("- Multiple reg resources for MMC node")
        print("- Two distinct resources as required")
        print("- Proper resource validation")
        print("- Address and size validation")
        print("- Resource type distinction")
    else:
        print("\n✗ MMC resource tests failed!")

    return success

if __name__ == "__main__":
    main()