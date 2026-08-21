import unittest

from app.correlation import (
    AddressCorrelation,
    AddressMatchType,
    CorrelatedDevice,
    CorrelationMatchMethod,
    CorrelationService,
    CorrelationWarning,
    IomemCandidate,
    OfNodePathNormalizer,
)
from app.model.addressing import AddressingReport, TranslatedAddressRange
from app.model.devicetree import DeviceTree, DeviceTreeNode
from app.runtime import IomemRegion, RuntimeDevice, RuntimeDriver


SERIAL_PATH = "/soc/serial@e6e60000"
GPIO_PATH = "/soc/gpio@e6050000"
I2C_PATH = "/soc/i2c@e6500000"
CAN_PATH = "/soc/can@e6c30000"


class CorrelationCoreTest(unittest.TestCase):
    def test_of_node_normalizer_converts_sysfs_path_to_dt_path(self) -> None:
        normalizer = OfNodePathNormalizer()

        self.assertEqual(
            normalizer.normalize("/sys/firmware/devicetree/base"),
            "/",
        )
        self.assertEqual(
            normalizer.normalize(
                "/sys/firmware/devicetree/base/soc/serial@e6e60000/"
            ),
            SERIAL_PATH,
        )
        self.assertIsNone(normalizer.normalize("/sys/devices/platform/serial/of_node"))

    def test_correlates_device_driver_and_exact_iomem_region(self) -> None:
        device = _runtime_device(
            driver_name="sh-sci",
            driver_path="/sys/bus/platform/drivers/sh-sci",
            of_node_sysfs_path=(
                "/sys/firmware/devicetree/base/soc/serial@e6e60000"
            ),
        )
        driver = RuntimeDriver(
            name="sh-sci",
            sysfs_path="/sys/bus/platform/drivers/sh-sci",
            bus="platform",
            bound_device_paths=(device.sysfs_path,),
        )
        translation = _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100)
        iomem = IomemRegion(
            start=0xE6E6_0000,
            end=0xE6E6_00FF,
            name="e6e60000.serial",
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(device,),
            drivers=(driver,),
            iomem=(iomem,),
        )

        self.assertEqual(report.warnings, ())
        self.assertEqual(len(report.devices), 1)
        correlated = report.devices[0]
        self.assertEqual(correlated.dt_node_path, SERIAL_PATH)
        self.assertIs(correlated.runtime_device, device)
        self.assertIs(correlated.runtime_driver, driver)
        self.assertEqual(
            correlated.match_method,
            CorrelationMatchMethod.EXACT_OF_NODE,
        )
        self.assertEqual(correlated.static_regions, (translation,))
        self.assertEqual(correlated.address_matches[0].match_type, AddressMatchType.EXACT)
        self.assertEqual(correlated.address_matches[0].iomem_name, "e6e60000.serial")
        self.assertEqual(
            correlated.address_matches[0].candidates,
            (
                IomemCandidate(
                    start=0xE6E6_0000,
                    end=0xE6E6_00FF,
                    name="e6e60000.serial",
                ),
            ),
        )

    def test_driver_association_falls_back_to_driver_name(self) -> None:
        device = _runtime_device(driver_name="sh-sci")
        driver = RuntimeDriver(
            name="sh-sci",
            sysfs_path="/sys/bus/platform/drivers/sh-sci",
            bus="platform",
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(driver,),
            iomem=(),
        )

        self.assertIs(report.devices[0].runtime_driver, driver)
        self.assertEqual(report.warnings, ())

    def test_unsupported_of_node_path_is_unmatched_with_warning(self) -> None:
        device = _runtime_device(
            of_node_sysfs_path="/sys/devices/platform/e6e60000.serial/of_node"
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(),
            iomem=(),
        )

        self.assertIsNone(report.devices[0].dt_node_path)
        self.assertEqual(
            report.devices[0].match_method,
            CorrelationMatchMethod.UNMATCHED,
        )
        self.assertEqual(report.warnings[0].code, "OF_NODE_PATH_UNSUPPORTED")

    def test_missing_dt_node_from_of_node_is_unmatched_with_warning(self) -> None:
        device = _runtime_device(
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/missing@0"
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(),
            iomem=(),
        )

        self.assertIsNone(report.devices[0].dt_node_path)
        self.assertEqual(report.warnings[0].code, "OF_NODE_DT_NODE_NOT_FOUND")
        self.assertEqual(report.warnings[0].dt_node_path, "/soc/missing@0")

    def test_runtime_device_without_of_node_remains_unmatched_without_warning(self) -> None:
        device = _runtime_device()

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(),
            iomem=(),
        )

        self.assertIsNone(report.devices[0].dt_node_path)
        self.assertEqual(
            report.devices[0].match_method,
            CorrelationMatchMethod.UNMATCHED,
        )
        self.assertEqual(report.warnings, ())

    def test_unmatched_dt_translation_still_gets_address_correlation(self) -> None:
        translation = _translation(GPIO_PATH, start=0xE605_0000, size=0x200)
        iomem = IomemRegion(
            start=0xE605_0000,
            end=0xE605_01FF,
            name="e6050000.gpio",
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(),
            drivers=(),
            iomem=(iomem,),
        )

        self.assertEqual(len(report.devices), 1)
        correlated = report.devices[0]
        self.assertEqual(correlated.dt_node_path, GPIO_PATH)
        self.assertIsNone(correlated.runtime_device)
        self.assertEqual(correlated.static_regions, (translation,))
        self.assertEqual(correlated.address_matches[0].match_type, AddressMatchType.EXACT)
        self.assertEqual(correlated.address_matches[0].iomem_name, "e6050000.gpio")

    def test_address_matching_reports_directional_contains_overlap_and_none(self) -> None:
        translations = (
            _translation(SERIAL_PATH, start=0x1000, size=0x100),
            _translation(GPIO_PATH, start=0x2000, size=0x1000),
            _translation(I2C_PATH, start=0x5000, size=0x100),
            _translation(CAN_PATH, start=0x7000, size=0x1000),
        )
        iomem = (
            IomemRegion(start=0x1000, end=0x1FFF, name="serial-window"),
            IomemRegion(start=0x2800, end=0x3FFF, name="gpio-overlap"),
            IomemRegion(start=0x7800, end=0x78FF, name="can-child"),
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=translations),
            devices=(),
            drivers=(),
            iomem=iomem,
        )
        by_path = {device.dt_node_path: device for device in report.devices}

        self.assertEqual(
            by_path[SERIAL_PATH].address_matches[0].match_type,
            AddressMatchType.IOMEM_CONTAINS_DT,
        )
        self.assertEqual(
            by_path[GPIO_PATH].address_matches[0].match_type,
            AddressMatchType.OVERLAP,
        )
        self.assertEqual(
            by_path[I2C_PATH].address_matches[0].match_type,
            AddressMatchType.NONE,
        )
        self.assertEqual(
            by_path[CAN_PATH].address_matches[0].match_type,
            AddressMatchType.DT_CONTAINS_IOMEM,
        )

    def test_ambiguous_address_match_adds_warning(self) -> None:
        translation = _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100)
        iomem = (
            IomemRegion(start=0xE6E6_0000, end=0xE6E6_00FF, name="serial-a"),
            IomemRegion(start=0xE6E6_0000, end=0xE6E6_00FF, name="serial-b"),
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(),
            drivers=(),
            iomem=iomem,
        )

        self.assertEqual(
            report.devices[0].address_matches[0].match_type,
            AddressMatchType.AMBIGUOUS,
        )
        self.assertEqual(
            report.devices[0].address_matches[0].candidates,
            (
                IomemCandidate(
                    start=0xE6E6_0000,
                    end=0xE6E6_00FF,
                    name="serial-a",
                ),
                IomemCandidate(
                    start=0xE6E6_0000,
                    end=0xE6E6_00FF,
                    name="serial-b",
                ),
            ),
        )
        self.assertEqual(report.warnings[0].code, "ADDRESS_MATCH_AMBIGUOUS")

    def test_iomem_incomplete_does_not_report_none_match(self) -> None:
        translation = _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100)

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(),
            drivers=(),
            iomem=(),
            iomem_complete=False,
        )

        self.assertEqual(
            report.devices[0].address_matches[0].match_type,
            AddressMatchType.UNAVAILABLE,
        )
        self.assertEqual(report.devices[0].address_matches[0].candidates, ())

    def test_iomem_incomplete_still_uses_positive_matches(self) -> None:
        translations = (
            _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100),
            _translation(I2C_PATH, start=0xE650_0000, size=0x100),
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=translations),
            devices=(),
            drivers=(),
            iomem=(
                IomemRegion(
                    start=0xE6E6_0000,
                    end=0xE6E6_00FF,
                    name="e6e60000.serial",
                ),
            ),
            iomem_complete=False,
        )
        by_path = {device.dt_node_path: device for device in report.devices}

        self.assertEqual(
            by_path[SERIAL_PATH].address_matches[0].match_type,
            AddressMatchType.EXACT,
        )
        self.assertEqual(
            by_path[I2C_PATH].address_matches[0].match_type,
            AddressMatchType.UNAVAILABLE,
        )

    def test_devices_incomplete_marks_dt_only_correlation_unavailable(self) -> None:
        translation = _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100)

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(),
            drivers=(),
            iomem=(
                IomemRegion(
                    start=0xE6E6_0000,
                    end=0xE6E6_00FF,
                    name="e6e60000.serial",
                ),
            ),
            devices_complete=False,
        )

        self.assertEqual(
            report.devices[0].match_method,
            CorrelationMatchMethod.UNAVAILABLE,
        )
        self.assertIsNone(report.devices[0].runtime_device)
        self.assertEqual(
            report.devices[0].address_matches[0].match_type,
            AddressMatchType.EXACT,
        )

    def test_devices_incomplete_still_uses_positive_runtime_device_matches(self) -> None:
        device = _runtime_device(
            of_node_sysfs_path=(
                "/sys/firmware/devicetree/base/soc/serial@e6e60000"
            ),
        )
        translations = (
            _translation(SERIAL_PATH, start=0xE6E6_0000, size=0x100),
            _translation(GPIO_PATH, start=0xE605_0000, size=0x100),
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=translations),
            devices=(device,),
            drivers=(),
            iomem=(),
            devices_complete=False,
        )
        by_path = {device.dt_node_path: device for device in report.devices}

        self.assertEqual(
            by_path[SERIAL_PATH].match_method,
            CorrelationMatchMethod.EXACT_OF_NODE,
        )
        self.assertEqual(
            by_path[GPIO_PATH].match_method,
            CorrelationMatchMethod.UNAVAILABLE,
        )

    def test_drivers_incomplete_does_not_report_driver_not_found(self) -> None:
        device = _runtime_device(
            driver_name="sh-sci",
            driver_path="/sys/bus/platform/drivers/sh-sci",
            of_node_sysfs_path=(
                "/sys/firmware/devicetree/base/soc/serial@e6e60000"
            ),
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(),
            iomem=(),
            drivers_complete=False,
        )

        self.assertIsNone(report.devices[0].runtime_driver)
        self.assertEqual(report.devices[0].warnings, ())
        self.assertEqual(report.warnings, ())

    def test_drivers_incomplete_still_uses_positive_driver_matches(self) -> None:
        device = _runtime_device(
            driver_name="sh-sci",
            driver_path="/sys/bus/platform/drivers/sh-sci",
        )
        driver = RuntimeDriver(
            name="sh-sci",
            sysfs_path="/sys/bus/platform/drivers/sh-sci",
            bus="platform",
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(),
            devices=(device,),
            drivers=(driver,),
            iomem=(),
            drivers_complete=False,
        )

        self.assertIs(report.devices[0].runtime_driver, driver)
        self.assertEqual(report.warnings, ())

    def test_unresolved_dt_translation_adds_warning_without_address_match(self) -> None:
        translation = TranslatedAddressRange(
            node_path=SERIAL_PATH,
            bus_address=0xE6E6_0000,
            cpu_address=None,
            size=0x100,
        )

        report = CorrelationService().correlate(
            tree=_tree(),
            addressing=AddressingReport(translations=(translation,)),
            devices=(),
            drivers=(),
            iomem=(),
        )

        self.assertEqual(report.devices[0].address_matches, ())
        self.assertEqual(report.warnings[0].code, "DT_REGION_UNRESOLVED")

    def test_correlation_model_validates_basic_contract(self) -> None:
        with self.assertRaises(ValueError):
            CorrelationWarning(
                code="BAD",
                message="bad path",
                dt_node_path="soc/serial@0",
            )

        with self.assertRaises(ValueError):
            IomemCandidate(start=0x2000, end=0x1000, name="bad")

        with self.assertRaises(ValueError):
            AddressCorrelation(
                dt_start=0x2000,
                dt_end=0x1000,
                iomem_start=None,
                iomem_end=None,
                iomem_name=None,
                match_type=AddressMatchType.NONE,
            )

        address_match = AddressCorrelation(
            dt_start=0,
            dt_end=0,
            iomem_start=None,
            iomem_end=None,
            iomem_name=None,
            match_type="none",
        )
        correlated = CorrelatedDevice(
            dt_node_path="/soc/test@0",
            runtime_device=None,
            runtime_driver=None,
            address_matches=[address_match],
            warnings=[],
        )

        self.assertEqual(correlated.address_matches, (address_match,))
        self.assertEqual(correlated.match_method, CorrelationMatchMethod.UNMATCHED)


def _tree() -> DeviceTree:
    serial = DeviceTreeNode(
        name="serial",
        path=SERIAL_PATH,
        unit_address="e6e60000",
        parent_path="/soc",
    )
    gpio = DeviceTreeNode(
        name="gpio",
        path=GPIO_PATH,
        unit_address="e6050000",
        parent_path="/soc",
    )
    i2c = DeviceTreeNode(
        name="i2c",
        path=I2C_PATH,
        unit_address="e6500000",
        parent_path="/soc",
    )
    can = DeviceTreeNode(
        name="can",
        path=CAN_PATH,
        unit_address="e6c30000",
        parent_path="/soc",
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        children=(serial, gpio, i2c, can),
    )
    root = DeviceTreeNode(name="/", path="/", children=(soc,))
    return DeviceTree(root=root)


def _runtime_device(
    *,
    driver_name: str | None = None,
    driver_path: str | None = None,
    of_node_sysfs_path: str | None = None,
) -> RuntimeDevice:
    return RuntimeDevice(
        name="e6e60000.serial",
        sysfs_path="/sys/bus/platform/devices/e6e60000.serial",
        bus="platform",
        driver_name=driver_name,
        driver_path=driver_path,
        of_node_sysfs_path=of_node_sysfs_path,
    )


def _translation(
    node_path: str,
    *,
    start: int,
    size: int,
) -> TranslatedAddressRange:
    return TranslatedAddressRange(
        node_path=node_path,
        bus_address=start,
        cpu_address=start,
        size=size,
    )


if __name__ == "__main__":
    unittest.main()
