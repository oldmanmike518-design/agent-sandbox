from __future__ import annotations

import uuid

# Process boot identity. Generated once at import time and held for the
# process lifetime. Observations record it; a boot-ID change during a
# verification run is verifier-caused (see docs/VERIFICATION_PIVOT_DESIGN.md §4.4).
BOOT_ID: str = str(uuid.uuid4())
