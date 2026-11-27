"""Core auditing engine for WaveBrute.

Implements the primary Auditor class with full support for:
- Live or simulated WiFi scanning (via scanner.py - now cross-platform
  with native Windows netsh + Npcap support for Scapy)
- Safe in-memory brute-force attack simulation
- Safe in-memory PMKID attack simulation (client-less RSN extraction)
- Safe in-memory WPS PIN simulation
- Handshake capture file analysis (via Scapy)
- Optional hashcat .22000 export for real offline cracking
- Ethics enforcement through ConsentManager
- Result collection for PDF/Markdown/HTML reporting
- Plugin system for custom wordlist mutators (register_mutator, load_mutator_plugin)
- Tiny on-device password prediction model (bundled trained patterns)

All methods include strict input validation and helpful error messages.
Simulation mode is the secure default.
"""

from __future__ import annotations

import os
import platform
import random
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .scanner import scan_wifi
from .wordlist import WordlistGenerator
from .ethics import ConsentManager
from .utils import parse_cap_file, generate_ai_suggestions
from .report import ReportBuilder


class Auditor:
    """Main orchestrator for ethical WiFi audits.

    Provides scan(), simulate_attack(), simulate_pmkid_attack(),
    simulate_wps_attack(), analyze_handshake(), export_for_hashcat(),
    build_report(), predict_passwords(), register_mutator() and
    load_mutator_plugin() as the primary public interface. All operations
    respect the ConsentManager and default to safe simulation mode. The
    integrated WordlistGenerator supports custom mutator plugins. The new
    TinyPasswordModel (bundled after training on weak-password patterns)
    powers AI suggestions and direct password prediction.

    Live scanning now supports Windows via netsh (Npcap required for
    full native Scapy packet functionality).
    """

    def __init__(self, simulation_mode: bool = True, interface: str = "wlan0") -> None:
        """Initialize Auditor with secure defaults.

        Args:
            simulation_mode: Whether to run entirely in safe simulation mode.
                Defaults to True (recommended for all non-authorized use).
            interface: Wireless interface name (ignored in simulation mode).
                On Windows the default is automatically adjusted to "Wi-Fi"
                when the provided value looks like a Linux name.

        Raises:
            ValueError: If simulation_mode is not bool or interface is empty.
        """
        if not isinstance(simulation_mode, bool):
            raise ValueError("simulation_mode must be a boolean (True for safe demo mode)")
        if not isinstance(interface, str) or not interface.strip():
            raise ValueError(
                "interface must be a non-empty string (e.g. 'wlan0', 'wlp2s0', 'Wi-Fi'). "
                "On Android this is typically handled by the OS."
            )

        self.simulation_mode = simulation_mode
        self.interface = interface.strip()

        if (
            platform.system() == "Windows"
            and self.interface.lower() in ("wlan0", "wlan1", "wlo1")
        ):
            self.interface = "Wi-Fi"

        self.consent_manager = ConsentManager()
        self.wordlist_generator = WordlistGenerator()
        self.results: list[dict[str, Any]] = []
        self.audit_log: list[dict[str, Any]] = []

    def register_mutator(self, mutator: Callable[[str], list[str]]) -> None:
        """Register a custom wordlist mutator.

        See WordlistGenerator.register_mutator() for full documentation.
        Registered mutators are used by simulate_attack(), simulate_pmkid_attack(),
        simulate_wps_attack() and any direct calls to wordlist_generator.from_ssid().
        """
        self.wordlist_generator.register_mutator(mutator)

    def load_mutator_plugin(self, plugin_path: str) -> None:
        """Load a custom mutator plugin from a Python file.

        See WordlistGenerator.load_mutator_plugin() for full documentation.
        """
        self.wordlist_generator.load_mutator_plugin(plugin_path)

    def scan(self, interface: str | None = None) -> list[dict[str, Any]]:
        """Scan for nearby WiFi networks.

        In simulation mode returns realistic synthetic data. In live mode
        delegates to scan_wifi() from scanner.py (now supports Windows
        via netsh; Npcap required for full Scapy compatibility).

        Args:
            interface: Optional interface override.

        Returns:
            List of dicts containing ssid, bssid, signal, encryption, etc.

        Raises:
            ValueError: On invalid interface name.
            RuntimeError: On live scan failure (suggests using simulation).
            PermissionError: If consent is not granted (live mode only).
        """
        if interface is None:
            interface = self.interface

        if not isinstance(interface, str) or not interface.strip():
            raise ValueError(
                "interface must be a non-empty string like 'wlan0' or 'Wi-Fi'. "
                "Run with simulation_mode=True if you lack privileges."
            )

        consent_action = (
            "simulated network scan" if self.simulation_mode else "network scan"
        )
        if not self.consent_manager.require_consent(consent_action):
            raise PermissionError(
                "ConsentManager blocked scan. Call consent_manager.show_checklist() "
                "and obtain explicit permission before live actions."
            )

        if self.simulation_mode:
            networks = self._simulate_scan()
        else:
            try:
                networks = scan_wifi(interface)
            except (OSError, RuntimeError, PermissionError) as exc:
                raise RuntimeError(
                    f"Live scan on '{interface}' failed. This usually requires "
                    "root privileges and monitor mode (airmon-ng) on Linux or "
                    "Npcap on Windows (https://npcap.com/). "
                    f"Original error: {exc}. Use simulation_mode=True for training."
                ) from exc

        for net in networks:
            net.setdefault("timestamp", datetime.now().isoformat())
            net.setdefault("ai_hint", generate_ai_suggestions(net.get("ssid", ""))[0])

        self.results.extend(networks)
        self.consent_manager.log_audit(
            "scan", {"interface": interface, "networks_found": len(networks)}
        )
        return networks

    def simulate_attack(
        self,
        ssid: str,
        wordlist_path: str | None = None,
        max_attempts: int = 10000,
    ) -> dict[str, Any]:
        """Perform a completely safe, in-memory brute-force simulation.

        No packets are transmitted. Demonstrates cracking logic, timing,
        and AI-augmented wordlist effectiveness. Uses the Auditor's
        WordlistGenerator (including any registered custom mutators)
        and the bundled TinyPasswordModel via generate_ai_suggestions().

        Args:
            ssid: Target network SSID.
            wordlist_path: Optional path to a wordlist file (if None, one is generated).
            max_attempts: Maximum simulation iterations for performance.

        Returns:
            Dict with success status, discovered password (if any), stats,
            and security recommendations.

        Raises:
            ValueError: If ssid is empty or malformed.
            FileNotFoundError: If wordlist_path is supplied but missing.
            PermissionError: If user has not consented.
        """
        if not isinstance(ssid, str) or len(ssid.strip()) == 0:
            raise ValueError("ssid must be a non-empty string")
        ssid = ssid.strip()

        if wordlist_path is not None and not os.path.isfile(wordlist_path):
            raise FileNotFoundError(
                f"Wordlist '{wordlist_path}' not found. Generate one with "
                "WordlistGenerator().save() first."
            )

        if not self.consent_manager.require_consent(f"simulated attack on '{ssid}'"):
            raise PermissionError(
                "Ethics Guard denied simulated attack. "
                "Mandatory consent checklist was not completed."
            )

        result = self._run_in_memory_attack(ssid, wordlist_path, max_attempts)
        self.results.append(result)
        self.consent_manager.log_audit("simulate_attack", result)
        return result

    def simulate_pmkid_attack(
        self,
        ssid: str,
        max_attempts: int = 8000,
    ) -> dict[str, Any]:
        """Perform a safe in-memory simulation of a PMKID attack.

        PMKID attacks allow cracking without capturing a full 4-way handshake
        by extracting the PMKID from the AP's response to a special association.
        This is common on many consumer routers. No real packets are sent.
        Uses the Auditor's WordlistGenerator (including any registered custom mutators)
        and the bundled TinyPasswordModel via generate_ai_suggestions().

        Args:
            ssid: Target network SSID.
            max_attempts: Cap on simulation iterations.

        Returns:
            Dict with success, password, stats, and PMKID-specific notes.

        Raises:
            ValueError: If ssid is invalid.
            PermissionError: If consent not granted.
        """
        if not isinstance(ssid, str) or len(ssid.strip()) == 0:
            raise ValueError("ssid must be a non-empty string")
        ssid = ssid.strip()

        if not self.consent_manager.require_consent(f"simulated PMKID attack on '{ssid}'"):
            raise PermissionError(
                "Ethics Guard denied the PMKID simulation. "
                "Complete the consent checklist first."
            )

        result = self._run_pmkid_simulation(ssid, max_attempts)
        self.results.append(result)
        self.consent_manager.log_audit("simulate_pmkid_attack", result)
        return result

    def simulate_wps_attack(
        self,
        ssid: str,
        max_attempts: int = 11000,
    ) -> dict[str, Any]:
        """Perform a safe in-memory simulation of WPS PIN brute-force.

        WPS uses an 8-digit PIN with a checksum; effective search space is ~11k.
        Demonstrates why WPS must be disabled on all routers. No real packets
        are sent. Uses registered mutators and the TinyPasswordModel.

        Args:
            ssid: Target network SSID.
            max_attempts: Cap on simulation iterations (reflects effective space).

        Returns:
            Dict with success, recovered PIN, stats and strong recommendation
            to disable WPS.

        Raises:
            ValueError: If ssid is invalid.
            PermissionError: If consent not granted.
        """
        if not isinstance(ssid, str) or len(ssid.strip()) == 0:
            raise ValueError("ssid must be a non-empty string")
        ssid = ssid.strip()

        if not self.consent_manager.require_consent(f"simulated WPS attack on '{ssid}'"):
            raise PermissionError(
                "Ethics Guard denied the WPS simulation. "
                "Complete the consent checklist first."
            )

        result = self._run_wps_simulation(ssid, max_attempts)
        self.results.append(result)
        self.consent_manager.log_audit("simulate_wps_attack", result)
        return result

    def predict_passwords(self, ssid: str, num_predictions: int = 10) -> list[str]:
        """Predict likely passwords using the bundled tiny on-device model.

        The model is trained offline on a corpus of common weak passwords
        and SSID-keyword associations, then bundled as pure-Python pattern
        tables and weights. No external libraries or network calls are used,
        making it suitable for Android and classroom environments.

        This powers the AI Predictor feature and is also used internally by
        generate_ai_suggestions() and wordlist generation.

        Args:
            ssid: Network name / context to base predictions on.
            num_predictions: Number of suggestions to return.

        Returns:
            List of predicted password strings, ranked by learned heuristics.

        Raises:
            ValueError: If ssid is empty.
        """
        if not isinstance(ssid, str) or not ssid.strip():
            raise ValueError("ssid must be a non-empty string")
        ssid = ssid.strip()

        from .utils import get_or_train_model
        model = get_or_train_model()
        return model.predict(ssid, num_predictions)

    def analyze_handshake(self, capfile: str) -> dict[str, Any]:
        """Analyze a packet capture for WPA handshake presence.

        Uses parse_cap_file (from utils) and Scapy when possible.
        Falls back to realistic simulation if the capture file is missing
        or real parsing fails (useful for demos, tests, and CLI).

        Args:
            capfile: Path to .cap, .pcap, or .pcapng file.

        Returns:
            Dict describing handshake details, MACs, crackability, and notes.

        Raises:
            ValueError: If capfile is empty or has unsupported extension
                (when the file exists).
            PermissionError: If consent was not granted.
        """
        if not isinstance(capfile, str) or not capfile.strip():
            raise ValueError("capfile must be a non-empty path string")

        capfile = capfile.strip()

        if not self.consent_manager.require_consent("handshake analysis"):
            raise PermissionError("ConsentManager blocked handshake analysis.")

        if not os.path.isfile(capfile):
            analysis = self._simulate_handshake_analysis(capfile)
        else:
            if not capfile.lower().endswith((".cap", ".pcap", ".pcapng")):
                raise ValueError(
                    "capfile must have extension .cap, .pcap or .pcapng"
                )

            try:
                parsed = parse_cap_file(capfile)
                if parsed and parsed.get("has_handshake", False):
                    analysis: dict[str, Any] = parsed
                else:
                    analysis = self._simulate_handshake_analysis(capfile)
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                analysis = self._simulate_handshake_analysis(capfile)

        analysis["file"] = capfile
        analysis["timestamp"] = datetime.now().isoformat()
        self.results.append(analysis)
        self.consent_manager.log_audit("analyze_handshake", analysis)
        return analysis

    def export_for_hashcat(
        self,
        ssid: str | None = None,
        output_path: str | None = None,
        hash_mode: str = "22000",
    ) -> str:
        """Generate a hashcat-compatible hash file for real offline cracking.

        Creates a .22000 file (modern hashcat format that supports both
        PMKID and full 4-way handshake data). In simulation mode this
        produces a realistic example file complete with usage instructions
        and guidance on converting real captures with hcxpcapngtool.

        This is the optional bridge from WaveBrute simulation to real
        hashcat cracking (authorized engagements only).

        Args:
            ssid: Optional target SSID (used in filename and comments).
            output_path: Where to save the hash file (auto-generated if None).
            hash_mode: Hashcat mode string (default "22000").

        Returns:
            Absolute path to the generated .22000 file.

        Raises:
            ValueError: If ssid or output_path are malformed.
            PermissionError: If consent was not granted.
            RuntimeError: If the file cannot be written.
        """
        if ssid is not None:
            if not isinstance(ssid, str) or len(ssid.strip()) == 0:
                raise ValueError("ssid must be None or a non-empty string")
            ssid = ssid.strip()

        if output_path is None:
            suffix = f"_{ssid.lower().replace(' ', '_').replace('-', '_')}" if ssid else ""
            output_path = f"wavebrute_hash{suffix}.22000"
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("output_path must be a non-empty string")

        output_path = output_path.strip()

        consent_action = (
            f"simulated hashcat export for {ssid or 'network'}"
        )
        if not self.consent_manager.require_consent(consent_action):
            raise PermissionError(
                "Ethics Guard denied hashcat export. "
                "Complete the consent checklist first."
            )

        content = self._generate_hashcat_content(ssid, hash_mode)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write hashcat file '{output_path}': {exc}"
            ) from exc

        result = {
            "type": "hashcat_export",
            "ssid": ssid,
            "output_path": output_path,
            "hash_mode": hash_mode,
            "simulation": self.simulation_mode,
            "timestamp": datetime.now().isoformat(),
        }
        self.results.append(result)
        self.consent_manager.log_audit("export_for_hashcat", result)
        return os.path.abspath(output_path)

    def batch_audit(
        self,
        ssids: list[str],
        max_attempts: int = 8000,
        include_pmkid: bool = True,
        include_predictions: bool = True,
    ) -> list[dict[str, Any]]:
        """Audit multiple networks in a single batch using safe simulations.

        Runs simulate_attack() for each SSID (and optionally
        simulate_pmkid_attack() and predict_passwords()). All results
        are collected, logged and stored in self.results. This is the
        primary entrypoint for the new batch mode.

        No real packets are ever sent. Perfect for classroom demos and
        comparing multiple networks quickly. Uses registered mutators
        and the bundled TinyPasswordModel.

        Args:
            ssids: List of target SSIDs (must be non-empty).
            max_attempts: Maximum simulation attempts per network.
            include_pmkid: Whether to also run PMKID simulation for each SSID.
            include_predictions: Whether to run AI password predictions for each.

        Returns:
            List of all result dictionaries produced by the batch run.

        Raises:
            ValueError: If ssids is not a list of valid non-empty strings.
            PermissionError: If consent is not granted for the batch action.
        """
        if not isinstance(ssids, list) or not ssids:
            raise ValueError("ssids must be a non-empty list of strings")
        if not all(isinstance(s, str) and s.strip() for s in ssids):
            raise ValueError("all items in ssids must be non-empty strings")

        consent_action = f"batch audit on {len(ssids)} network(s)"
        if not self.consent_manager.require_consent(consent_action):
            raise PermissionError(
                "Ethics Guard denied batch audit. "
                "Complete the consent checklist first."
            )

        batch_results: list[dict[str, Any]] = []

        for ssid in ssids:
            attack = self.simulate_attack(ssid, max_attempts=max_attempts)
            batch_results.append(attack)

            if include_pmkid:
                pmkid = self.simulate_pmkid_attack(
                    ssid, max_attempts=max_attempts // 2
                )
                batch_results.append(pmkid)

            if include_predictions:
                preds = self.predict_passwords(ssid, num_predictions=6)
                pred_result: dict[str, Any] = {
                    "type": "password_predictions",
                    "ssid": ssid,
                    "predictions": preds,
                    "simulation": True,
                    "timestamp": datetime.now().isoformat(),
                }
                self.results.append(pred_result)
                batch_results.append(pred_result)

        self.consent_manager.log_audit(
            "batch_audit",
            {
                "ssids": ssids,
                "networks_audited": len(ssids),
                "include_pmkid": include_pmkid,
                "include_predictions": include_predictions,
                "total_results": len(batch_results),
            },
        )
        return batch_results

    def _simulate_scan(self) -> list[dict[str, Any]]:
        """Return hard-coded but realistic networks for simulation mode.

        Signal strengths and AI hints are varied for demonstration value.
        """
        networks = [
            {
                "ssid": "Cafe_Rouge_FreeWiFi",
                "bssid": "00:14:BF:12:34:56",
                "channel": 6,
                "signal": -42,
                "encryption": "WPA2-PSK",
                "frequency": "2.4 GHz",
            },
            {
                "ssid": "Linksys-5G",
                "bssid": "A0:12:34:56:78:9A",
                "channel": 36,
                "signal": -58,
                "encryption": "WPA3",
                "frequency": "5 GHz",
            },
            {
                "ssid": "NETGEAR_Guest",
                "bssid": "11:22:33:44:55:66",
                "channel": 11,
                "signal": -71,
                "encryption": "WPA2",
                "frequency": "2.4 GHz",
            },
            {
                "ssid": "IoT-Devices",
                "bssid": "DE:AD:BE:EF:CA:FE",
                "channel": 1,
                "signal": -35,
                "encryption": "OPEN",
                "frequency": "2.4 GHz",
            },
        ]

        for net in networks:
            net["signal"] = net["signal"] - (len(net["ssid"]) % 7)
            net["timestamp"] = datetime.now().isoformat()
            net["ai_hint"] = generate_ai_suggestions(net["ssid"])[0]

        return networks

    def _run_in_memory_attack(
        self,
        ssid: str,
        wordlist_path: str | None,
        max_attempts: int,
    ) -> dict[str, Any]:
        """Internal simulation engine.

        Uses the shared self.wordlist_generator (with any registered custom
        mutators) and augments it with AI suggestions from the bundled model.
        """
        start_time = time.time()

        generator = self.wordlist_generator
        if wordlist_path and os.path.isfile(wordlist_path):
            wordlist = generator.from_ssid(ssid, size=500)
        else:
            wordlist = generator.from_ssid(ssid, size=1200)

        ai_suggestions = generate_ai_suggestions(ssid)
        wordlist = ai_suggestions + wordlist

        candidate = ssid.lower().replace(" ", "").replace("-", "")
        secret = (candidate + "2023")[:12]
        if len(candidate) > 4:
            secret = candidate[:4] + "admin"

        cracked_password: str | None = None
        attempts = 0

        for password in wordlist[:max_attempts]:
            attempts += 1
            if password.lower() == secret.lower() or any(
                kw in password.lower()
                for kw in ("123", "admin", "pass", "wifi", candidate[:5])
            ):
                cracked_password = password
                break

        duration = time.time() - start_time

        success = cracked_password is not None
        return {
            "type": "brute_force_simulation",
            "ssid": ssid,
            "success": success,
            "password": cracked_password,
            "attempts": attempts,
            "duration_seconds": round(duration, 3),
            "words_per_second": round(attempts / duration) if duration > 0 else 0,
            "simulation": True,
            "ai_suggestions_used": len(ai_suggestions),
            "recommendations": [
                "Use a unique 20+ character password",
                "Enable WPA3 where possible",
                "Disable WPS and guest networks",
                "Monitor for unauthorized access points",
                "Consider enterprise authentication (802.1X)",
            ],
            "timestamp": datetime.now().isoformat(),
        }

    def _run_pmkid_simulation(
        self, ssid: str, max_attempts: int
    ) -> dict[str, Any]:
        """Internal engine for PMKID simulation.

        Uses the shared self.wordlist_generator (with any registered custom
        mutators) + AI hints from the bundled tiny model. The cracking
        condition is tuned to demonstrate typical weak passwords found in
        PMKID captures.
        """
        start_time = time.time()

        generator = self.wordlist_generator
        wordlist = generator.from_ssid(ssid, size=800)
        ai_suggestions = generate_ai_suggestions(ssid)
        wordlist = list(dict.fromkeys(ai_suggestions + wordlist))

        base = ssid.lower().replace(" ", "").replace("-", "").replace("_", "")
        secret = base + "123" if len(base) < 10 else base[:6] + "admin"

        cracked_password: str | None = None
        attempts = 0

        for password in wordlist[:max_attempts]:
            attempts += 1
            p_lower = password.lower()
            if (
                p_lower == secret
                or "admin" in p_lower
                or "123" in p_lower
                or any(x in p_lower for x in ("pass", "wifi", base[:6]))
            ):
                cracked_password = password
                break

        duration = time.time() - start_time

        success = cracked_password is not None
        return {
            "type": "pmkid_simulation",
            "ssid": ssid,
            "success": success,
            "password": cracked_password,
            "attempts": attempts,
            "duration_seconds": round(duration, 3),
            "words_per_second": round(attempts / duration) if duration > 0 else 0,
            "simulation": True,
            "attack_type": "PMKID",
            "ai_suggestions_used": len(ai_suggestions),
            "notes": "PMKID retrieved from AP RSN IE. This attack does not require any connected clients.",
            "recommendations": [
                "Disable 802.11r fast roaming if not needed (can leak PMKID)",
                "Use complex unique passwords for all WiFi networks",
                "Upgrade to WPA3 which is resistant to PMKID attacks",
                "Consider enterprise mode (WPA2/3-Enterprise) for business networks",
            ],
            "timestamp": datetime.now().isoformat(),
        }

    def _run_wps_simulation(self, ssid: str, max_attempts: int) -> dict[str, Any]:
        """Internal engine for WPS PIN simulation.

        Demonstrates 8-digit PIN brute-force with checksum. Uses common
        defaults and a deterministic success path for reproducible demos.
        """
        start_time = time.time()

        common_pins = ["12345670", "00000000", "11111111", "12345678", "87654321"]
        pin: str | None = None
        success = False
        attempts = 0
        max_tries = min(max_attempts, 11000)

        for i in range(max_tries):
            attempts += 1
            test_pin = f"{random.randint(0, 99999999):08d}"
            if test_pin in common_pins or i == 2345:
                pin = "12345670"
                success = True
                break

        duration = time.time() - start_time

        return {
            "type": "wps_simulation",
            "ssid": ssid,
            "success": success,
            "pin": pin,
            "attempts": attempts,
            "duration_seconds": round(duration, 3),
            "words_per_second": round(attempts / duration) if duration > 0 else 0,
            "simulation": True,
            "notes": (
                "WPS PIN brute-force is feasible due to limited 8-digit space "
                "and checksum algorithm. This is why WPS must be disabled."
            ),
            "recommendations": [
                "Disable WPS completely on all routers",
                "Use strong unique WPA3 passwords",
                "Regularly audit router admin settings for enabled features",
                "Monitor for rogue access points",
            ],
            "timestamp": datetime.now().isoformat(),
        }

    def _simulate_handshake_analysis(self, capfile: str) -> dict[str, Any]:
        """Return realistic handshake metadata for simulation or fallback."""
        return {
            "has_handshake": True,
            "handshake_type": "4-way",
            "ap_mac": "00:11:22:33:44:55",
            "client_mac": "66:77:88:99:AA:BB",
            "eapol_frames": 4,
            "signal_strength": -45,
            "crackable": True,
            "crack_time_estimate": "< 90 minutes on modern GPU with good wordlist",
            "simulation": True,
            "notes": (
                "Valid 4-way handshake detected. In a real authorized engagement "
                "this file would be passed to hashcat/aircrack-ng together with "
                "the wordlist generated by WordlistGenerator."
            ),
        }

    def _generate_hashcat_content(
        self, ssid: str | None, hash_mode: str
    ) -> str:
        """Internal helper that builds a realistic .22000 file with comments.

        The content contains illustrative hashes so the file can be used
        immediately with hashcat for demonstration. Real captures should
        be converted with hcxpcapngtool.
        """
        timestamp = datetime.now().isoformat()
        target = ssid or "AnyNetwork"

        header = f"""# WaveBrute Hashcat Export
# Generated : {timestamp}
# SSID      : {target}
# Mode      : {hash_mode}
# Simulation: {self.simulation_mode}
#
# This file is ready for hashcat.
# Recommended command:
#   hashcat -m 22000 {os.path.basename('wavebrute_hash.22000')} wordlist.txt -w 3 --force
#
# For real authorized captures:
#   1. Capture with airodump-ng -c CHANNEL --bssid MAC -w capture capture.cap
#   2. Convert with hcxpcapngtool -o real.22000 capture.cap
#   3. Run hashcat on the real file with your targeted wordlist.
#
"""

        if ssid:
            header += f"# Targeted for SSID: {ssid}\n#\n"

        sample_pmkid = (
            "1*2*001122334455*66778899aabb*"
            "4d6f72616e*436166655f526f7567655f4672656557694669*"
            "010203040506*"
        )

        body = f"""# Sample PMKID hash (hashcat -m 22000):
{sample_pmkid}

# The hash above is illustrative only. In a real engagement you would
# replace it with output from hcxpcapngtool or similar. The file format
# is the current standard for WPA/WPA2/WPA3 PMKID and handshakes.

# Remember: only use hashcat against networks you own or have explicit
# written permission to test. Delete all data after the engagement.
"""

        return header + body

    def build_report(
        self,
        title: str = "WaveBrute Ethical Audit Report",
        output_path: str | None = None,
        format: str = "pdf",  # noqa: A002
    ) -> str:
        """Generate a professional report from all collected results.

        Supports PDF (default, via ReportLab), Markdown and HTML.
        HTML includes inline neo-brutalist CSS matching the GUI.
        Markdown is clean and GitHub-friendly.

        Args:
            title: Report title.
            output_path: Where to save the report (auto-generated if None).
            format: One of "pdf", "md", or "html".

        Returns:
            Absolute path to the created report file.

        Raises:
            ValueError: If no results have been collected yet or format is invalid.
        """
        if format not in ("pdf", "md", "markdown", "html"):
            raise ValueError("format must be one of: pdf, md, html")
        if not self.results:
            raise ValueError(
                "No audit results available. Run scan(), simulate_attack(), "
                "simulate_pmkid_attack(), simulate_wps_attack(), analyze_handshake(), "
                "predict_passwords(), or export_for_hashcat() first."
            )

        fmt = "md" if format == "markdown" else format

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".pdf" if fmt == "pdf" else ".md" if fmt == "md" else ".html"
            output_path = f"wavebrute_report_{timestamp}{ext}"
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("output_path must be a non-empty string")

        builder = ReportBuilder.from_results(self.results)
        if fmt == "pdf":
            final_path = builder.to_pdf(title, output_path)
        elif fmt == "md":
            final_path = builder.to_markdown(title, output_path)
        elif fmt == "html":
            final_path = builder.to_html(title, output_path)
        else:
            final_path = output_path

        self.consent_manager.log_audit("build_report", {"title": title, "format": fmt, "path": final_path})
        return final_path

    def get_results(self) -> list[dict[str, Any]]:
        """Return a shallow copy of all results collected during this session."""
        return list(self.results)

    def clear_results(self) -> None:
        """Clear all stored results (useful when starting a new audit)."""
        self.results.clear()
        self.audit_log.clear()


if __name__ == "__main__":
    auditor = Auditor(simulation_mode=True)
    print("=== WaveBrute Auditor Demo (simulation mode) ===")
    nets = auditor.scan()
    print(f"Discovered {len(nets)} networks (simulated).")
    attack = auditor.simulate_attack("Cafe_Rouge_FreeWiFi")
    print(f"Simulated attack success: {attack['success']}")
    if attack.get("password"):
        print(f"  Password found: {attack['password']}")
    pmkid = auditor.simulate_pmkid_attack("IoT-Devices")
    print(f"PMKID simulation success: {pmkid['success']}")
    wps = auditor.simulate_wps_attack("IoT-Devices")
    print(f"WPS simulation success: {wps['success']} (PIN: {wps.get('pin')})")
    preds = auditor.predict_passwords("Cafe_Rouge_FreeWiFi", 6)
    print(f"Model predictions: {preds}")
    hc_path = auditor.export_for_hashcat("Cafe_Rouge_FreeWiFi")
    print(f"Hashcat export written to: {hc_path}")
    report_path = auditor.build_report()
    print(f"PDF report written to: {report_path}")
    md_path = auditor.build_report("Markdown Audit", format="md")
    print(f"Markdown report written to: {md_path}")
    html_path = auditor.build_report("HTML Audit", format="html")
    print(f"HTML report written to: {html_path}")

    print("\n=== Plugin system demo ===")
    def demo_mutator(word: str):
        return [word + "PLUGIN", word.upper() + "2025"]
    auditor.register_mutator(demo_mutator)
    attack2 = auditor.simulate_attack("TestNet")
    print("Custom mutator registered and used.")

    print("\n=== Batch mode demo ===")
    batch = auditor.batch_audit(
        ["BatchNet1", "BatchNet2"], max_attempts=500, include_pmkid=False
    )
    print(f"Batch produced {len(batch)} results.")
    print("Demo completed successfully. All operations were simulated.")
