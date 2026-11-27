"""Android entry point for WaveBrute."""

import os
import sys

# The repository uses a src/ package layout; expose it to the bundled runtime.
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from wavebrute.gui.app import WaveBruteApp  # noqa: E402


if __name__ == "__main__":
    WaveBruteApp(simulation_mode=True, dark_theme=True).run()
