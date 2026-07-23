import struct
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_processor import DataProcessor
from extra_calculations import ExtraCalculations


class PVSSignedValueTests(unittest.TestCase):
    @staticmethod
    def _float_hex(value):
        return "0x" + struct.pack(">f", value).hex().upper()

    def test_negative_pvs_counter_is_preserved_as_negative_amp_hours(self):
        processor = DataProcessor(endianness="big")
        result = processor.parse_data(
            f"BP_PVS,{self._float_hex(135.0)},{self._float_hex(-3_600_000.0)}"
        )

        self.assertEqual(result["BP_PVS_milliamp*s"], -3_600_000.0)
        self.assertEqual(result["BP_PVS_Ah"], -1.0)

    def test_negative_pvs_charge_does_not_exceed_physical_pack_capacity(self):
        remaining = ExtraCalculations().calculate_remaining_capacity_from_ah(
            used_ah=0.0,
            total_capacity_ah=40.0,
            bp_pvs_ah=-5.0,
        )

        self.assertEqual(remaining, 40.0)


if __name__ == "__main__":
    unittest.main()
