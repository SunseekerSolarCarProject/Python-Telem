import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_processor import DataProcessor


class IMUAndElevationTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.processor = DataProcessor()

    def test_nav_parses_gps_elevation_and_satellite_status_fields(self):
        result = self.processor.parse_data(
            "NAV,IMU_MPH=24.31,GPS_MPH=24.10,GPS_VALID=1,"
            "VEHICLE_MPH=24.31,SOURCE=CAN,LAT=42.291707,LON=-85.587229,"
            "FIX=3,AGE_MS=120,ELEV_M=214.372,ELEV_VALID=1,ELEV_AGE_MS=84,"
            "SATS_VISIBLE=11,SATS_VISIBLE_VALID=1,SATS_VISIBLE_AGE_MS=287,"
            "SATS_USED=8,SATS_USED_VALID=1,SATS_USED_AGE_MS=306"
        )

        self.assertAlmostEqual(result["NAV_ELEV_M"], 214.372)
        self.assertEqual(result["NAV_ELEV_VALID"], 1)
        self.assertEqual(result["NAV_ELEV_AGE_MS"], 84)
        self.assertEqual(result["NAV_SATS_VISIBLE"], 11)
        self.assertEqual(result["NAV_SATS_VISIBLE_VALID"], 1)
        self.assertEqual(result["NAV_SATS_VISIBLE_AGE_MS"], 287)
        self.assertEqual(result["NAV_SATS_USED"], 8)
        self.assertEqual(result["NAV_SATS_USED_VALID"], 1)
        self.assertEqual(result["NAV_SATS_USED_AGE_MS"], 306)

    def test_imu_g_parses_complete_firmware_sample(self):
        result = self.processor.parse_data(
            "IMU_G,VALID=1,CALIBRATED=1,MOUNT_VALID=1,FORWARD_G=0.184,"
            "LINEAR_X_G=0.021,LINEAR_Y_G=0.184,LINEAR_Z_G=-0.012,"
            "TOTAL_G=1.018,DYNAMIC_G=0.186,PEAK_BOOT_G=0.438,AGE_MS=4"
        )

        self.assertEqual(result["IMU_G_VALID"], 1)
        self.assertEqual(result["IMU_G_CALIBRATED"], 1)
        self.assertEqual(result["IMU_G_MOUNT_VALID"], 1)
        self.assertAlmostEqual(result["IMU_FORWARD_G"], 0.184)
        self.assertAlmostEqual(result["IMU_LINEAR_X_G"], 0.021)
        self.assertAlmostEqual(result["IMU_LINEAR_Y_G"], 0.184)
        self.assertAlmostEqual(result["IMU_LINEAR_Z_G"], -0.012)
        self.assertAlmostEqual(result["IMU_TOTAL_G"], 1.018)
        self.assertAlmostEqual(result["IMU_DYNAMIC_G"], 0.186)
        self.assertAlmostEqual(result["IMU_PEAK_BOOT_G"], 0.438)
        self.assertEqual(result["IMU_G_AGE_MS"], 4)

    def test_older_nav_without_elevation_remains_compatible(self):
        result = self.processor.parse_data(
            "NAV,GPS_VALID=1,LAT=42.0,LON=-85.0,FIX=3,AGE_MS=10"
        )

        self.assertEqual(result["NAV_ELEV_VALID"], 0)
        self.assertEqual(result["NAV_ELEV_AGE_MS"], 0)
        self.assertEqual(result["NAV_SATS_VISIBLE"], 0)
        self.assertEqual(result["NAV_SATS_VISIBLE_VALID"], 0)
        self.assertEqual(result["NAV_SATS_VISIBLE_AGE_MS"], 0)
        self.assertEqual(result["NAV_SATS_USED"], 0)
        self.assertEqual(result["NAV_SATS_USED_VALID"], 0)
        self.assertEqual(result["NAV_SATS_USED_AGE_MS"], 0)


if __name__ == "__main__":
    unittest.main()
