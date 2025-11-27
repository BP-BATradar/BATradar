import os
import sys
import sounddevice as sd

EXPECTED_POSITION_ORDER = ['bottom_left', 'bottom_right', 'top_left', 'top_right']

MIC_PORT_MAPPING = {
    'bottom_left': [
        {'controller': 'xhci-hcd.0', 'endpoint': '1-1:1.0'},
        'platform-xhci-hcd.0-usb-0:1:1.0',
    ],
    'top_left': [
        {'controller': 'xhci-hcd.1', 'endpoint': '3-1:1.0'},
        'platform-xhci-hcd.1-usb-0:1:1.0',
    ],
    'top_right': [
        {'controller': 'xhci-hcd.0', 'endpoint': '1-2:1.0'},
        'platform-xhci-hcd.0-usb-0:2:1.0',
    ],
    'bottom_right': [
        {'controller': 'xhci-hcd.1', 'endpoint': '3-2:1.0'},
        'platform-xhci-hcd.1-usb-0:2:1.0',
    ],
}


def _extract_alsa_card_index(device_name: str):
    marker = "hw:"
    if marker not in device_name:
        return None
    start = device_name.find(marker) + len(marker)
    end = start
    while end < len(device_name) and device_name[end].isdigit():
        end += 1
    if end == start:
        return None
    try:
        return int(device_name[start:end])
    except ValueError:
        return None


def _ensure_list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _port_spec_matches(port_spec, syspath: str) -> bool:
    path = syspath.replace('\\', '/')
    base = os.path.basename(path)

    if isinstance(port_spec, dict):
        controller = port_spec.get('controller')
        if controller and controller not in path:
            return False

        endpoint = port_spec.get('endpoint')
        if endpoint and endpoint != base:
            return False

        usb_bus = port_spec.get('usb_bus')
        if usb_bus and f"/{usb_bus}/" not in path:
            return False

        contains = port_spec.get('contains')
        if contains:
            tokens = contains if isinstance(contains, (list, tuple)) else [contains]
            for token in tokens:
                if token not in path:
                    return False
        return True

    port_str = str(port_spec)
    if port_str in path:
        return True

    spec_base = os.path.basename(port_str)
    if spec_base and spec_base == base:
        return True

    return False


def _find_alsa_card_for_port(port_spec):
    base = "/sys/class/sound"
    if not os.path.isdir(base):
        return None

    for entry in os.listdir(base):
        if not entry.startswith("card"):
            continue
        try:
            card_idx = int(entry[4:])
        except ValueError:
            continue

        dev_link = os.path.join(base, entry, "device")
        if not os.path.islink(dev_link):
            continue

        target = os.path.realpath(dev_link)
        if _port_spec_matches(port_spec, target):
            return card_idx

    return None


def _find_sd_device_for_card(devices, card_idx: int):
    card_str = f"hw:{card_idx},"
    for idx, device in enumerate(devices):
        if device['max_input_channels'] <= 0:
            continue
        name = device.get('name', '')
        if card_str in name:
            return idx, name
    return None


def _debug_print_input_devices_and_ports():
    base = "/sys/class/sound"
    devices = sd.query_devices()

    print("Detected input devices and their ALSA ports:")
    for idx, device in enumerate(devices):
        if device['max_input_channels'] <= 0:
            continue
        name = device.get('name', '')
        card_idx = _extract_alsa_card_index(name)
        port_info = "UNKNOWN"
        if card_idx is not None and os.path.isdir(base):
            dev_link = os.path.join(base, f"card{card_idx}", "device")
            if os.path.islink(dev_link):
                port_info = os.path.realpath(dev_link)
        print(f"  [{idx}] {name} -> {port_info}")
    print()


def find_device_by_port(port_spec) -> tuple:
    port_specs = _ensure_list(port_spec)
    devices = sd.query_devices()

    if sys.platform.startswith("linux") and os.path.isdir("/sys/class/sound"):
        for spec in port_specs:
            card_idx = _find_alsa_card_for_port(spec)
            if card_idx is None:
                continue
            result = _find_sd_device_for_card(devices, card_idx)
            if result is not None:
                return result

    for spec in port_specs:
        if not isinstance(spec, str):
            continue
        for idx, device in enumerate(devices):
            if device['max_input_channels'] == 0:
                continue
            device_name = device.get('name', '')
            if spec in device_name:
                return idx, device_name

    if sys.platform.startswith("linux"):
        _debug_print_input_devices_and_ports()

    error_msg = f"Device with specified port mapping {port_specs} not found.\nAvailable input devices:\n"
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            error_msg += f"  [{idx}] {device.get('name', 'Unknown')}\n"
    raise ValueError(error_msg)


def _gather_mic_mapping(verbose: bool = False):
    if verbose:
        print("=" * 70)
        print("AUTOMATIC MICROPHONE SELECTION BY USB PORT")
        print("=" * 70)
        print("Using hardcoded USB port mapping:")
        if sys.platform.startswith("linux"):
            _debug_print_input_devices_and_ports()

    mapped_indices = []
    mapped_names = []
    
    for position in EXPECTED_POSITION_ORDER:
        port_spec = MIC_PORT_MAPPING[position]
        device_idx, device_name = find_device_by_port(port_spec)
        mapped_indices.append(device_idx)
        mapped_names.append(device_name)
        if verbose:
            print(f"  {position:>12}: [{device_idx}] {device_name}")
            print(f"              Port spec: {port_spec}")

    if verbose:
        print("=" * 70)

    return mapped_indices, mapped_names


def select_and_map_microphones():
    return _gather_mic_mapping(verbose=True)


def ensure_mic_configuration(current_indices=None, current_names=None):
    mapped_indices, mapped_names = _gather_mic_mapping(verbose=False)
    changed = (
        current_indices is None
        or current_names is None
        or mapped_indices != current_indices
        or mapped_names != current_names
    )
    return mapped_indices, mapped_names, changed


if __name__ == "__main__":
    try:
        select_and_map_microphones()
        print("\nMicrophone mapping check complete.")
    except Exception as e:
        print(f"\nError during microphone selection: {e}")
        sys.exit(1)

