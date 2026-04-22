"""GPU information retrieval for NVIDIA, AMD, and Intel GPUs.

Supports selecting a specific GPU by card number (matching /sys/class/drm/cardN).
"Auto" tries nvidia-smi first, then scans sysfs for AMD/Intel.
"""

import glob
import os
import subprocess
from functools import cache

from services.platform_info import IS_LINUX, SUBPROCESS_FLAGS


# Internal helpers


def _nvidia_query(query: str, device_id: int | None = None) -> str | None:
    """Run an nvidia-smi query, return stripped output or None."""
    cmd = ["nvidia-smi"]
    if device_id is not None:
        cmd.append(f"--id={device_id}")
    cmd.extend([f"--query-gpu={query}", "--format=csv,noheader,nounits"])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _read_sysfs(path: str) -> str | None:
    """Read and strip a sysfs file, return None on failure."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _find_hwmon(device_dir: str) -> str | None:
    """Find the first hwmon directory under a device."""
    dirs = sorted(glob.glob(os.path.join(device_dir, "hwmon", "hwmon*")))
    return dirs[0] if dirs else None


@cache
def _card_info(card_num: int) -> tuple[str | None, str | None, str | None]:
    """Look up a specific card in sysfs. Returns (card_path, device_dir, driver)."""
    if not IS_LINUX:
        return None, None, None
    card_path = f"/sys/class/drm/card{card_num}"
    device_dir = os.path.join(card_path, "device")
    uevent = os.path.join(device_dir, "uevent")
    try:
        with open(uevent) as f:
            for line in f:
                if line.startswith("DRIVER="):
                    return card_path, device_dir, line.strip().split("=", 1)[1]
    except OSError:
        pass
    return None, None, None


@cache
def _first_sysfs_gpu() -> tuple[str | None, str | None, str | None]:
    """Find the first AMD/Intel GPU in sysfs."""
    if not IS_LINUX:
        return None, None, None
    for card_path in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        if not os.path.basename(card_path).removeprefix("card").isdigit():
            continue
        device_dir = os.path.join(card_path, "device")
        uevent = os.path.join(device_dir, "uevent")
        try:
            with open(uevent) as f:
                for line in f:
                    if line.startswith("DRIVER="):
                        driver = line.strip().split("=", 1)[1]
                        if driver in ("amdgpu", "i915", "xe"):
                            return card_path, device_dir, driver
        except OSError:
            continue
    return None, None, None


def _pci_slot(device_dir: str) -> str | None:
    """Read PCI_SLOT_NAME from a device's uevent."""
    uevent = os.path.join(device_dir, "uevent")
    try:
        with open(uevent) as f:
            for line in f:
                if line.startswith("PCI_SLOT_NAME="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return None


@cache
def _nvidia_id_for_pci(pci: str) -> int | None:
    """Find nvidia-smi device index matching a sysfs PCI slot name."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,pci.bus_id",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode != 0:
            return None
        # Compare bus:device.function (ignore domain length differences)
        pci_suffix = pci.lower().rsplit(":", 2)
        pci_key = ":".join(pci_suffix[-2:]) if len(pci_suffix) >= 2 else pci.lower()
        for line in result.stdout.strip().splitlines():
            parts = line.split(",")
            if len(parts) == 2:
                bus_suffix = parts[1].strip().lower().rsplit(":", 2)
                bus_key = ":".join(bus_suffix[-2:]) if len(bus_suffix) >= 2 else ""
                if pci_key == bus_key:
                    return int(parts[0].strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _resolve(card: str):
    """Resolve a card selection to (card_path, device_dir, driver, nvidia_id).

    card: "Auto" or a card number like "0", "1".
    """
    if card == "Auto" or not card:
        return (*_first_sysfs_gpu(), None)

    # Accept "0 (amdgpu)" format from dropdown or plain "0"
    card = card.split()[0]
    try:
        card_num = int(card)
    except ValueError:
        return None, None, None, None

    card_path, device_dir, driver = _card_info(card_num)
    if not driver:
        return None, None, None, None

    if driver == "nvidia":
        pci = _pci_slot(device_dir)
        nv_id = _nvidia_id_for_pci(pci) if pci else None
        return card_path, device_dir, driver, nv_id

    return card_path, device_dir, driver, None


# Public API


@cache
def _gpu_name(card_num: int, device_dir: str, driver: str) -> str:
    """Get a human-readable GPU name."""
    # NVIDIA: nvidia-smi gives clean marketing names
    if driver == "nvidia":
        val = _nvidia_query("name")
        if val:
            return val

    # All vendors: try lspci with the PCI slot
    pci = _pci_slot(device_dir)
    if pci:
        try:
            result = subprocess.run(
                ["lspci", "-s", pci],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Format: "0c:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Raphael (rev cb)"
                # or:     "01:00.0 VGA compatible controller: NVIDIA Corporation GA102 [GeForce RTX 3080] (rev a1)"
                line = result.stdout.strip()
                if ": " in line:
                    desc = line.split(": ", 1)[-1]
                    # Strip trailing revision
                    if "(rev " in desc:
                        desc = desc[:desc.rindex("(rev ")].strip()
                    # NVIDIA: last bracket has the product name
                    if "NVIDIA" in desc and "[" in desc:
                        return desc[desc.rindex("[") + 1:desc.rindex("]")]
                    # AMD: product name follows the [AMD/ATI] vendor tag
                    if ("[AMD" in desc or "[ATI" in desc) and "]" in desc:
                        after = desc[desc.index("]") + 1:].strip()
                        if after:
                            return f"AMD {after}"
                    # Intel: similar bracket pattern
                    if "Intel" in desc and "]" in desc:
                        after = desc[desc.index("]") + 1:].strip()
                        if after:
                            return f"Intel {after}"
                        # Fallback: text between brackets
                        return desc[desc.index("[") + 1:desc.index("]")]
                    return desc
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return driver


@cache
def available_gpus() -> list[str]:
    """Return dropdown options like ["Auto", "0 (GeForce RTX 3080)"]."""
    options = ["Auto"]
    if not IS_LINUX:
        return options
    for card_path in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        name = os.path.basename(card_path)
        num = name.removeprefix("card")
        if not num.isdigit():
            continue
        _, device_dir, driver = _card_info(int(num))
        if driver:
            label = _gpu_name(int(num), device_dir, driver)
            options.append(f"{num} ({label})")
    return options


def get_utilization(card: str = "Auto") -> str | None:
    """GPU utilization as a numeric string (no %)."""
    card_path, device_dir, driver, nv_id = _resolve(card)

    if card == "Auto" or driver == "nvidia":
        val = _nvidia_query("utilization.gpu", nv_id)
        if val is not None:
            return val

    if driver == "amdgpu" and device_dir:
        val = _read_sysfs(os.path.join(device_dir, "gpu_busy_percent"))
        if val is not None:
            return val

    # Intel has no non-root utilization metric in sysfs
    return None


def get_clock(card: str = "Auto") -> str | None:
    """GPU clock speed in MHz as a numeric string (no units)."""
    card_path, device_dir, driver, nv_id = _resolve(card)

    if card == "Auto" or driver == "nvidia":
        val = _nvidia_query("clocks.gr", nv_id)
        if val is not None:
            return val

    if not card_path:
        return None

    # AMD: pp_dpm_sclk – active line marked with *
    if driver == "amdgpu":
        content = _read_sysfs(os.path.join(device_dir, "pp_dpm_sclk"))
        if content:
            for line in content.splitlines():
                if "*" in line:
                    for part in line.split():
                        cleaned = part.lower().replace("mhz", "")
                        if cleaned.isdigit():
                            return cleaned
                    break

    # Intel i915
    if driver == "i915":
        val = _read_sysfs(os.path.join(card_path, "gt_cur_freq_mhz"))
        if val is not None and val.isdigit():
            return val

    # Intel xe: per-tile gt frequency
    if driver == "xe":
        for gt in sorted(glob.glob(
                os.path.join(device_dir, "tile*", "gt*", "freq*"))):
            val = _read_sysfs(os.path.join(gt, "cur_freq"))
            if val is not None and val.isdigit():
                return val

    return None


def get_temperature(card: str = "Auto") -> str | None:
    """GPU temperature in °C as a numeric string (no units)."""
    card_path, device_dir, driver, nv_id = _resolve(card)

    if card == "Auto" or driver == "nvidia":
        val = _nvidia_query("temperature.gpu", nv_id)
        if val is not None:
            return val

    if not device_dir or not driver:
        return None

    # AMD and Intel expose temp through hwmon (millidegrees C)
    hwmon = _find_hwmon(device_dir)
    if hwmon:
        val = _read_sysfs(os.path.join(hwmon, "temp1_input"))
        if val is not None and val.lstrip("-").isdigit():
            return str(int(val) // 1000)

    return None
