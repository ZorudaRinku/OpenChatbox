import subprocess
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, SUBPROCESS_FLAGS


class VolumeToken:
    tag = "volume"
    field_defs = [
        FieldDef("suffix", "Suffix", "%"),
        FieldDef("muted_text", "Muted Text", "🔇 Muted"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        if IS_WINDOWS:
            return self._resolve_windows()
        return self._resolve_linux()

    def _resolve_linux(self) -> str:
        # Try wpctl (PipeWire/WirePlumber)
        try:
            result = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if "MUTED" in text:
                    return self.fields["muted_text"]
                vol = float(text.split(":")[1].strip().split()[0])
                return f"{vol * 100:.0f}{self.fields['suffix']}"
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
        # Fallback: pactl (PulseAudio)
        try:
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for part in result.stdout.split():
                    if "%" in part:
                        return part
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]

    def _resolve_windows(self) -> str:
        # Use PowerShell to query the Windows audio endpoint
        try:
            ps_script = (
                "Add-Type -TypeDefinition '"
                "using System.Runtime.InteropServices;"
                "[Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]"
                "interface IAudioEndpointVolume {"
                "  int _0(); int _1(); int _2(); int _3(); int _4(); int _5(); int _6(); int _7(); int _8(); int _9(); int _10(); int _11();"
                "  int GetMute(out bool bMute);"
                "  int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);"
                "  int GetMasterVolumeLevelScalar(out float pfLevel);"
                "}"
                "[Guid(\"D666063F-1587-4E43-81F1-B948E807363F\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]"
                "interface IMMDevice { int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface); }"
                "[Guid(\"A95664D2-9614-4F35-A746-DE8DB63617E6\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]"
                "interface IMMDeviceEnumerator { int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice); }"
                "[ComImport, Guid(\"BCDE0395-E52F-467C-8E3D-C4579291692E\")] class MMDeviceEnumerator {}"
                "';"
                "$enum = New-Object MMDeviceEnumerator;"
                "$dev = $null; $enum.GetDefaultAudioEndpoint(0, 1, [ref]$dev);"
                "$iid = [Guid]'5CDF2C82-841E-4546-9722-0CF74078229A';"
                "$aev = $null; $dev.Activate([ref]$iid, 1, [IntPtr]::Zero, [ref]$aev);"
                "$vol = 0.0; $aev.GetMasterVolumeLevelScalar([ref]$vol);"
                "$muted = $false; $aev.GetMute([ref]$muted);"
                "if ($muted) { 'MUTED' } else { [math]::Round($vol * 100) }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=5,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text == "MUTED":
                    return self.fields["muted_text"]
                return f"{text}{self.fields['suffix']}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
