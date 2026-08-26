import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.dependency import DependencyKind
from app.interrupts import (
    InterruptCorrelation,
    InterruptCorrelationReport,
    InterruptCorrelationResolution,
    InterruptCorrelationWarning,
)
from app.main import create_app
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    ParseResult,
    PropertyKind,
)
from app.runtime import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeInterrupt,
    RuntimeSystemInfo,
    RuntimeWarning,
)
from app.services.devicetree_state import DeviceTreeState


class FakeCollector:
    def __init__(self, result: ParseResult) -> None:
        self.result = result

    def collect_from_file(self, path: str | Path) -> ParseResult:
        return self.result


class FakeRuntimeProvider:
    def __init__(
        self,
        *,
        interrupts: RuntimeCollection[tuple[RuntimeInterrupt, ...]] | None = None,
    ) -> None:
        self.interrupts = interrupts or RuntimeCollection(data=())
        self.calls = {
            "system": 0,
            "devices": 0,
            "drivers": 0,
            "iomem": 0,
            "interrupts": 0,
        }

    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        self.calls["system"] += 1
        return RuntimeCollection(data=RuntimeSystemInfo())

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        self.calls["devices"] += 1
        return RuntimeCollection(data=())

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        self.calls["drivers"] += 1
        return RuntimeCollection(data=())

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        self.calls["iomem"] += 1
        return RuntimeCollection(data=())

    def collect_interrupts(self) -> RuntimeCollection[tuple[RuntimeInterrupt, ...]]:
        self.calls["interrupts"] += 1
        return self.interrupts


class FakeInterruptCorrelationService:
    def __init__(self, warning: InterruptCorrelationWarning) -> None:
        self.warning = warning

    def correlate(self, **kwargs: object) -> InterruptCorrelationReport:
        dependencies = kwargs["dependencies"]
        for dependency in dependencies:
            if dependency.kind == DependencyKind.INTERRUPT:
                return InterruptCorrelationReport(
                    correlations=(
                        InterruptCorrelation(
                            dependency=dependency,
                            resolution=InterruptCorrelationResolution.AMBIGUOUS,
                            warnings=(self.warning,),
                        ),
                    ),
                    warnings=(self.warning,),
                )
        return InterruptCorrelationReport(warnings=(self.warning,))


class FastApiDependencyTest(unittest.TestCase):
    def test_dependency_devices_returns_device_centric_json(self) -> None:
        provider = FakeRuntimeProvider(
            interrupts=RuntimeCollection(
                data=(
                    RuntimeInterrupt(
                        irq=214,
                        counts=(0, 4291, 0, 0),
                        controller="GICv3",
                        hardware_irq=182,
                        trigger="Level",
                        actions=("imr",),
                        metadata=(
                            (
                                "hardware_irq_source",
                                "/sys/kernel/irq/214/hwirq",
                            ),
                        ),
                    ),
                )
            )
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(len(body["data"]), 1)
        device = body["data"][0]
        self.assertEqual(device["dt_node_path"], "/soc/imr@e6260000")
        self.assertEqual(
            [dependency["kind"] for dependency in device["dependencies"]],
            ["clock", "iommu", "interrupt"],
        )

        clock = device["dependencies"][0]
        self.assertEqual(clock["provider_dt_path"], "/soc/cpg@e6150000")
        self.assertEqual(clock["provider_phandle"], 0x17)
        self.assertEqual(clock["specifier_cells"], [12, 4])
        self.assertEqual(clock["static_resolution"], "resolved")
        self.assertIsNone(clock["interrupt_resolution"])
        self.assertIsNone(clock["runtime_interrupt"])

        interrupt = device["dependencies"][2]
        self.assertEqual(
            interrupt["provider_dt_path"],
            "/soc/interrupt-controller@f1000000",
        )
        self.assertEqual(interrupt["static_resolution"], "resolved")
        self.assertEqual(interrupt["interrupt_resolution"], "resolved")
        self.assertEqual(interrupt["interrupt_match_method"], "controller_hardware_irq")
        self.assertEqual(interrupt["runtime_interrupt"]["irq"], 214)
        self.assertEqual(interrupt["runtime_interrupt"]["hardware_irq"], 182)
        self.assertEqual(interrupt["runtime_interrupt"]["total_count"], 4291)
        self.assertEqual(interrupt["runtime_interrupt"]["actions"], ["imr"])
        self.assertEqual(
            interrupt["runtime_interrupt"]["metadata"],
            [["hardware_irq_source", "/sys/kernel/irq/214/hwirq"]],
        )
        self.assertEqual(len(interrupt["runtime_candidates"]), 1)

    def test_dependency_devices_preserves_ambiguous_runtime_irq_candidates(
        self,
    ) -> None:
        irq_a = RuntimeInterrupt(
            irq=214,
            counts=(1,),
            controller="GICv3",
            hardware_irq=182,
        )
        irq_b = RuntimeInterrupt(
            irq=215,
            counts=(2,),
            controller="GICv3",
            hardware_irq=182,
        )
        provider = FakeRuntimeProvider(
            interrupts=RuntimeCollection(data=(irq_a, irq_b))
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 200)
        interrupt = response.json()["data"][0]["dependencies"][2]
        self.assertEqual(interrupt["interrupt_resolution"], "ambiguous")
        self.assertIsNone(interrupt["runtime_interrupt"])
        self.assertEqual(
            [candidate["irq"] for candidate in interrupt["runtime_candidates"]],
            [214, 215],
        )
        self.assertEqual(
            interrupt["interrupt_warnings"][0]["code"],
            "RUNTIME_INTERRUPT_MATCH_AMBIGUOUS",
        )

    def test_dependency_warnings_preserve_runtime_irq(self) -> None:
        warning = InterruptCorrelationWarning(
            code="IRQ_METADATA_AMBIGUOUS",
            message="IRQ metadata is ambiguous",
            consumer_dt_path="/soc/imr@e6260000",
            provider_dt_path="/soc/interrupt-controller@f1000000",
            runtime_irq=214,
            source_path="/sys/kernel/irq/214/hwirq",
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=FakeRuntimeProvider(),
                interrupt_correlation_service=FakeInterruptCorrelationService(
                    warning
                ),
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"][0]["runtime_irq"], 214)
        interrupt = body["data"][0]["dependencies"][2]
        self.assertEqual(interrupt["interrupt_warnings"][0]["runtime_irq"], 214)

    def test_dependency_devices_preserves_interrupt_unavailable_semantics(self) -> None:
        provider = FakeRuntimeProvider(
            interrupts=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="PROC_INTERRUPTS_READ_FAILED",
                        message="Unable to read /proc/interrupts",
                        source_path="/proc/interrupts",
                    ),
                ),
            )
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        interrupt = body["data"][0]["dependencies"][2]
        self.assertEqual(interrupt["static_resolution"], "resolved")
        self.assertEqual(interrupt["interrupt_resolution"], "unavailable")
        self.assertIsNone(interrupt["runtime_interrupt"])
        self.assertEqual(body["warnings"][0]["code"], "PROC_INTERRUPTS_READ_FAILED")

    def test_dependency_devices_returns_422_when_devicetree_parse_failed(self) -> None:
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="bad.dtb",
                    collector=FakeCollector(
                        ParseResult(
                            tree=None,
                            source="bad.dtb",
                            warnings=("best effort",),
                            errors=("Failed to parse DTB",),
                        )
                    ),
                ),
                runtime_provider=FakeRuntimeProvider(),
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["source"], "bad.dtb")
        self.assertEqual(response.json()["detail"]["warnings"], ["best effort"])
        self.assertEqual(response.json()["detail"]["errors"], ["Failed to parse DTB"])

    def test_dependency_endpoint_collects_only_runtime_interrupts(self) -> None:
        provider = FakeRuntimeProvider()
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/dependencies/devices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(provider.calls["interrupts"], 1)
        self.assertEqual(provider.calls["system"], 0)
        self.assertEqual(provider.calls["devices"], 0)
        self.assertEqual(provider.calls["drivers"], 0)
        self.assertEqual(provider.calls["iomem"], 0)

    def test_openapi_exposes_typed_dependency_contract(self) -> None:
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(),
                runtime_provider=FakeRuntimeProvider(),
            )
        )

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("DependencyDeviceCollectionResponse", schemas)
        self.assertIn("DeviceDependencyViewResponse", schemas)
        self.assertIn("DeviceDependencyResponse", schemas)
        self.assertIn("DependencyRuntimeInterruptResponse", schemas)
        self.assertIn(
            "metadata",
            schemas["DependencyRuntimeInterruptResponse"]["properties"],
        )
        self.assertIn(
            "runtime_irq",
            schemas["DependencyWarningResponse"]["properties"],
        )
        self.assertEqual(
            schemas["DeviceDependencyResponse"]["properties"][
                "static_resolution"
            ]["$ref"],
            "#/components/schemas/DependencyResolution",
        )
        self.assertEqual(
            schemas["DeviceDependencyResponse"]["properties"][
                "interrupt_resolution"
            ]["anyOf"][0]["$ref"],
            "#/components/schemas/InterruptCorrelationResolution",
        )
        self.assertEqual(
            response.json()["paths"]["/api/v1/dependencies/devices"]["get"][
                "responses"
            ]["200"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/DependencyDeviceCollectionResponse",
        )


def sample_tree() -> DeviceTree:
    gic = DeviceTreeNode(
        name="interrupt-controller",
        path="/soc/interrupt-controller@f1000000",
        unit_address="f1000000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(name="interrupt-controller", raw_bytes=b""),
            strings("compatible", "arm,gic-v3"),
            cells("#interrupt-cells", 3),
            cells("phandle", 1),
        ),
    )
    cpg = DeviceTreeNode(
        name="cpg",
        path="/soc/cpg@e6150000",
        unit_address="e6150000",
        parent_path="/soc",
        properties=(
            cells("phandle", 0x17),
            cells("#clock-cells", 2),
        ),
    )
    ipmmu = DeviceTreeNode(
        name="iommu",
        path="/soc/iommu@e6740000",
        unit_address="e6740000",
        parent_path="/soc",
        properties=(
            cells("phandle", 0x35),
            cells("#iommu-cells", 1),
        ),
    )
    imr = DeviceTreeNode(
        name="imr",
        path="/soc/imr@e6260000",
        unit_address="e6260000",
        parent_path="/soc",
        properties=(
            cells("clocks", 0x17, 12, 4),
            cells("iommus", 0x35, 3),
            cells("interrupts", 0, 150, 4),
        ),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(cells("interrupt-parent", 1),),
        children=(gic, cpg, ipmmu, imr),
    )
    root = DeviceTreeNode(name="/", path="/", children=(soc,))
    return DeviceTree(root=root)


def _devicetree_state(tree: DeviceTree) -> DeviceTreeState:
    return DeviceTreeState(
        current_path="board.dtb",
        collector=FakeCollector(ParseResult(tree=tree, source="board.dtb")),
    )


def cells(name: str, *values: int) -> DeviceTreeProperty:
    raw = b"".join(value.to_bytes(4, byteorder="big") for value in values)
    return DeviceTreeProperty(
        name=name,
        raw_bytes=raw,
        kind=PropertyKind.CELLS,
        value=values,
    )


def strings(name: str, *values: str) -> DeviceTreeProperty:
    raw = b"".join(value.encode("utf-8") + b"\x00" for value in values)
    kind = PropertyKind.STRING if len(values) == 1 else PropertyKind.STRING_LIST
    value: str | tuple[str, ...] = values[0] if len(values) == 1 else values
    return DeviceTreeProperty(
        name=name,
        raw_bytes=raw,
        kind=kind,
        value=value,
    )


if __name__ == "__main__":
    unittest.main()
