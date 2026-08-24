#!/usr/bin/env python3
"""Fair execution policy for the hardened official-source collector.

The underlying collector owns URL validation, SSRF protection, decoding, parsing and state.
This entrypoint only changes per-source/global limits so early sources cannot starve later
sources before duplicate filtering happens.
"""
from __future__ import annotations

import collect_official_sources as collector

# At most five items per source is enough for daily editorial discovery and guarantees that
# all enabled sources are traversed before global ranking. The underlying configuration has
# 20 sources today, so this bound remains comfortably below the generous global ceiling.
collector.MAX_PER_SOURCE = 5
collector.MAX_TOTAL = 1000


def main() -> int:
    return collector.main()


if __name__ == "__main__":
    raise SystemExit(main())
