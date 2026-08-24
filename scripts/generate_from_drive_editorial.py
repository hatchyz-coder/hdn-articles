#!/usr/bin/env python3
"""Compatibility entry point for the resilient Drive editorial publisher."""
from generate_from_drive_editorial_v3 import *  # noqa: F401,F403
from generate_from_drive_editorial_v3 import _depth_issues, _description, _state_key, _verify_approved_folder

if __name__ == "__main__":
    raise SystemExit(main())
