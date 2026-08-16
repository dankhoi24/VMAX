#!/usr/bin/env python3
"""
MMC Resources Test with Explicit Assertions
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

class TestMMCResourcesAssert(unittest.TestCase):
    """Test cases for MMC resources with explicit assertions"""

    def setUp(self):
        self.mmc_node = MMCNode("mmc0")

    def test_multiple_distinct_resources_assertion(self):
        """Test that we have 2 distinct resources as required"""
        # Add first resource - memory mapped I/O
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add second distinct resource - DMA or command registers
        resource2 = MMCResource("dma", 0x2000, 0x800, "dma")
        self.mmc_node.add_resource(resource2)

        # Assert we have exactly 2 resources
        resources = self.mmc_node.get_resources()
        self.assertEqual(len(resources), 2, "Should have exactly 2 resources")

        # Assert resources are distinct by address
        self.assertNotEqual(resources[0].address, resources[1].address,
                          "Resources should have different addresses")

        # Assert resources are distinct by name
        self.assertNotEqual(resources[0].name, resources[1].name,
                          "Resources should have different names")

        # Assert resources are distinct by type
        self.assertNotEqual(resources[0].type, resources[1].type,
                          "Resources should have different types")

        # Assert no overlapping
        self.assertTrue(
            resources[0].address + resources[0].size <= resources[1].address or
            resources[1].address + resources[1].size <= resources[0].address,
            "Resources should not overlap in address space"
        )

    def test_resource_properties_assertion(self):
        """Test specific resource properties with assertions"""
        # Add first resource
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        self.mmc_node.add_resource(resource1)

        # Add second resource
        resource2 = MMCResource("dma", 0x2000, 0x800, "dma")
        self.mmc_node.add_resource(resource2)

        # Test first resource properties
        self.assertEqual(resource1.name, "mmio")
        self.assertEqual(resource1.address, 0x1000)
        self.assertEqual(resource1.size, 0x1000)
        self.assertEqual(resource1.type, "memory")

        # Test second resource properties
        self.assertEqual(resource2.name, "dma")
        self.assertEqual(resource2.address, 0x2000)
        self.assertEqual(resource2.size, 0x800)
        self.assertEqual(resource2.type, "dma")

    def test_resource_validation_assertion(self):
        """Test resource validation with assertions"""
        # Add two non-overlapping resources
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        resource2 = MMCResource("dma", 0x3000, 0x800, "dma")
        self.mmc_node.add_resource(resource1)
        self.mmc_node.add_resource(resource2)

        # Validate resources should pass
        is_valid = self.mmc_node.validate_resources()
        self.assertTrue(is_valid, "Valid resources should pass validation")

    def test_overlapping_resources_detection(self):
        """Test that overlapping resources are detected"""
        # Add overlapping resources
        resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
        resource2 = MMCResource("dma", 0x1500, 0x800, "dma")  # Overlaps with resource1
        self.mmc_node.add_resource(resource1)
        self.mmc_node.add_resource(resource2)

        # Validation should fail due to overlap
        is_valid = self.mmc_node.validate_resources()
        self.assertFalse(is_valid, "Overlapping resources should fail validation")

def run_assertion_tests():
    """Run MMC resource tests with explicit assertions"""
    print("Running MMC Resources Tests with Assertions...")
    print("=" * 50)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMMCResourcesAssert)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()

def main():
    """Main function demonstrating MMC resource assertions"""
    print("MMC Resources Test with Assertions")
    print("=" * 35)

    # Create MMC node
    mmc_node = MMCNode("mmc0")

    # Add multiple resources as required by "multiple reg"
    print("Adding MMC resources (multiple reg):")

    # First resource (memory mapped I/O)
    resource1 = MMCResource("mmio", 0x1000, 0x1000, "memory")
    mmc_node.add_resource(resource1)
    print(f"  Resource 1: {resource1}")

    # Second resource (DMA or command registers)
    resource2 = MMCResource("dma", 0x2000, 0x800, "dma")
    mmc_node.add_resource(resource2)
    print(f"  Resource 2: {resource2}")

    # Verify resources are distinct as required
    resources = mmc_node.get_resources()

    # Assertions that must be true:
    print("\nAssertion Results:")
    print("-" * 20)

    # Assert 2 resources exist
    assert len(resources) == 2, f"Expected 2 resources, got {len(resources)}"
    print("✓ 2 resources present")

    # Assert resources are distinct by address
    assert resources[0].address != resources[1].address, "Resources should have different addresses"
    print("✓ Resources have distinct addresses")

    # Assert resources are distinct by name
    assert resources[0].name != resources[1].name, "Resources should have different names"
    print("✓ Resources have distinct names")

    # Assert resources are distinct by type
    assert resources[0].type != resources[1].type, "Resources should have different types"
    print("✓ Resources have distinct types")

    # Assert no overlapping
    assert (resources[0].address + resources[0].size <= resources[1].address or
            resources[1].address + resources[1].size <= resources[0].address), \
            "Resources should not overlap"
    print("✓ Resources don't overlap")

    # Run unit tests
    print("\n" + "=" * 50)
    success = run_assertion_tests()

    if success:
        print("\n✓ All assertion tests passed!")
        print("\nImplementation Summary:")
        print("- MMC node with multiple reg resources")
        print("- Two distinct resources as required")
        print("- Proper address/size/type handling")
        print("- Resource validation")
        print("- Explicit assertions for all requirements")
    else:
        print("\n✗ Some assertion tests failed!")

    return success

if __name__ == "__main__":
    main()