import unittest

from app.parsers.devicetree.decoder import PropertyDecoder
from app.model.devicetree import PropertyKind


class PropertyDecoderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.decoder = PropertyDecoder()

    def test_decodes_boolean_property_from_empty_bytes(self) -> None:
        prop = self.decoder.decode("dma-coherent", b"")

        self.assertEqual(prop.kind, PropertyKind.BOOLEAN)
        self.assertTrue(prop.value)
        self.assertEqual(prop.raw_bytes, b"")

    def test_decodes_compatible_as_string_list(self) -> None:
        prop = self.decoder.decode("compatible", b"vendor,device\x00vendor,fallback\x00")

        self.assertEqual(prop.kind, PropertyKind.STRING_LIST)
        self.assertEqual(prop.value, ("vendor,device", "vendor,fallback"))
        self.assertEqual(prop.to_dict()["value"], ["vendor,device", "vendor,fallback"])

    def test_decodes_single_compatible_as_string_list(self) -> None:
        prop = self.decoder.decode("compatible", b"renesas,r8a779g0\x00")

        self.assertEqual(prop.kind, PropertyKind.STRING_LIST)
        self.assertEqual(prop.value, ("renesas,r8a779g0",))
        self.assertEqual(prop.to_dict()["value"], ["renesas,r8a779g0"])

    def test_decodes_single_string_property(self) -> None:
        prop = self.decoder.decode("status", b"okay\x00")

        self.assertEqual(prop.kind, PropertyKind.STRING)
        self.assertEqual(prop.value, "okay")

    def test_decodes_empty_string_property(self) -> None:
        prop = self.decoder.decode("label", b"\x00")

        self.assertEqual(prop.kind, PropertyKind.STRING)
        self.assertEqual(prop.value, "")

    def test_decodes_u32_cells_as_big_endian_values(self) -> None:
        raw = bytes.fromhex("000000001234000000001000")
        prop = self.decoder.decode("reg", raw)

        self.assertEqual(prop.kind, PropertyKind.CELLS)
        self.assertEqual(prop.value, (0x00000000, 0x12340000, 0x00001000))
        self.assertEqual(prop.raw_bytes, raw)

    def test_known_cell_property_with_bad_length_is_unknown(self) -> None:
        prop = self.decoder.decode("reg", b"\x01\x02\x03")

        self.assertEqual(prop.kind, PropertyKind.UNKNOWN)
        self.assertIsNone(prop.value)
        self.assertEqual(prop.raw_bytes, b"\x01\x02\x03")

    def test_decodes_non_cell_binary_as_bytes(self) -> None:
        prop = self.decoder.decode("vendor,data", b"\x01\x02\x03")

        self.assertEqual(prop.kind, PropertyKind.BYTES)
        self.assertEqual(prop.value, (1, 2, 3))

    def test_invalid_utf8_with_trailing_nul_is_bytes(self) -> None:
        prop = self.decoder.decode("vendor,data", b"\xff\x00")

        self.assertEqual(prop.kind, PropertyKind.BYTES)
        self.assertEqual(prop.value, (0xFF, 0x00))

    def test_arbitrary_four_byte_binary_is_unknown_not_cells(self) -> None:
        raw = b"\x01\x02\x03\x04"
        prop = self.decoder.decode("vendor,data", raw)

        self.assertEqual(prop.kind, PropertyKind.UNKNOWN)
        self.assertIsNone(prop.value)
        self.assertEqual(prop.raw_bytes, raw)

    def test_decode_many_preserves_order(self) -> None:
        props = self.decoder.decode_many(
            (
                ("status", b"okay\x00"),
                ("#address-cells", bytes.fromhex("00000002")),
            )
        )

        self.assertEqual([prop.name for prop in props], ["status", "#address-cells"])
        self.assertEqual(props[1].value, (2,))


if __name__ == "__main__":
    unittest.main()
