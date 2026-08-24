import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = TimeoutError
    sys.modules["requests"] = requests_stub

import generate_from_drive_editorial as editorial


class DriveEditorialRequeueTests(unittest.TestCase):
    def test_exhausted_legacy_api_timeout_is_requeued_after_upgrade(self):
        doc = {"id": "legacy-timeout", "name": "LH8_記事1", "modifiedTime": "2026-08-20T00:00:00Z"}
        state = {
            "documents": {
                editorial._state_key(doc["id"]): {
                    "modifiedTime": doc["modifiedTime"],
                    "status": "api_timeout",
                    "retry_count": 99,
                }
            }
        }
        self.assertTrue(editorial.is_unprocessed_or_updated(state, doc))

    def test_exhausted_current_api_timeout_is_not_requeued_forever(self):
        doc = {"id": "current-timeout", "name": "LH8_記事2", "modifiedTime": "2026-08-20T00:00:00Z"}
        state = {
            "documents": {
                editorial._state_key(doc["id"]): {
                    "modifiedTime": doc["modifiedTime"],
                    "status": "api_timeout",
                    "retry_count": 99,
                    "processorVersion": editorial.PROCESSOR_VERSION,
                }
            }
        }
        self.assertFalse(editorial.is_unprocessed_or_updated(state, doc))


if __name__ == "__main__":
    unittest.main()
