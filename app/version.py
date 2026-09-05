"""Single source of truth for the DoKey version.

Logged as the first line of every run and shown in the help overlay.

To release: bump this, merge to main, then tag the merge commit with a matching
"v" prefix, e.g. `git tag v1.2.1 && git push origin v1.2.1`.
"""

VERSION = "1.2.1"
