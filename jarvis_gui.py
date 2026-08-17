#!/usr/bin/env python3
"""Jarvis GUI — panel de control flotante con GTK3.

Lanza Jarvis en background y muestra un panel con:
- Botón on/off (envía SIGUSR1/SIGUSR2 al proceso jarvis)
- Slider de sensibilidad del wake word (ajusta WAKE_THRESHOLD en runtime)
- Botón de documentación de comandos

Uso:
    python jarvis_gui.py              # lanza jarvis + GUI
    python jarvis_gui.py --no-launch  # solo GUI (jarvis ya corriendo)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

# --- Paths ---
JARVIS_ROOT = Path(__file__).resolve().parent
VENV_PY = JARVIS_ROOT / "jarvis" / ".venv" / "bin" / "python"
PID_FILE = Path.home() / ".local" / "state" / "jarvis" / "jarvis.pid"
FSM_STATE_FILE = Path.home() / ".local" / "state" / "jarvis" / "fsm_state"
STATE_FILE = Path.home() / ".local" / "share" / "jarvis" / "state.json"
DOCS_FILE = JARVIS_ROOT / "jarvis" / "docs" / "comandos_jarvis.md"

# FSM state → GUI label mapping
_FSM_LABELS = {
    "idle": ("● ESCUCHANDO", "Esperando 'JARVIS'...", "status-active"),
    "listening": ("● ESCUCHANDO", "Hable ahora...", "status-active"),
    "thinking": ("● PENSANDO", "Procesando...", "status-active"),
    "executing": ("● EJECUTANDO", "", "status-active"),
    "confirming": ("● CONFIRmando", "Esperando confirmación...", "status-active"),
    "speaking": ("● HABLANDO", "Jarvis responde...", "status-active"),
    "off": ("● APAGADO", "Modo off — diga 'jarvis on'", "status-inactive"),
}

# --- CSS ---
CSS = b"""
* {
    font-family: "Sans", "Ubuntu", sans-serif;
}

.window-bg {
    background-color: #1a1a2e;
}

.title-label {
    color: #e94560;
    font-size: 20px;
    font-weight: bold;
}

.subtitle-label {
    color: #a0a0b0;
    font-size: 11px;
}

.status-card {
    background-color: #16213e;
    border-radius: 8px;
    padding: 12px;
}

.status-active {
    color: #00b894;
    font-size: 14px;
    font-weight: bold;
}

.status-inactive {
    color: #d63031;
    font-size: 14px;
    font-weight: bold;
}

.status-detail {
    color: #a0a0b0;
    font-size: 11px;
}

.power-btn {
    background-color: #00b894;
    color: white;
    font-size: 14px;
    font-weight: bold;
    border-radius: 25px;
    padding: 12px 40px;
    border: none;
}

.power-btn:hover {
    background-color: #00a884;
}

.power-btn-off {
    background-color: #d63031;
}

.power-btn-off:hover {
    background-color: #c0392b;
}

.slider-card {
    background-color: #16213e;
    border-radius: 8px;
    padding: 10px;
}

.slider-label {
    color: white;
    font-size: 12px;
    font-weight: bold;
}

.slider-value {
    color: #00b894;
    font-size: 16px;
    font-weight: bold;
}

.slider-hint {
    color: #a0a0b0;
    font-size: 10px;
}

.btn-secondary {
    background-color: #0f3460;
    color: white;
    font-size: 12px;
    border-radius: 6px;
    padding: 8px 16px;
    border: none;
}

.btn-secondary:hover {
    background-color: #1a4a7a;
}

.provider-card {
    background-color: #16213e;
    border-radius: 8px;
    padding: 10px;
}

.provider-label {
    color: white;
    font-size: 12px;
    font-weight: bold;
}

.provider-hint {
    color: #a0a0b0;
    font-size: 10px;
}

.provider-active {
    color: #00b894;
    font-size: 11px;
    font-weight: bold;
}

/* --- Segmented pill selector --- */
.provider-pill-box {
    background-color: #0f3460;
    border-radius: 8px;
    padding: 3px;
}

.provider-pill {
    background-color: transparent;
    color: #a0a0b0;
    font-size: 11px;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 12px;
    border: none;
    min-width: 80px;
}

.provider-pill:hover {
    color: white;
    background-color: rgba(255, 255, 255, 0.08);
}

.provider-pill-active {
    background-color: #00b894;
    color: white;
    font-size: 11px;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 12px;
    border: none;
    min-width: 80px;
}

.provider-pill-active:hover {
    background-color: #00a884;
}

.log-card {
    background-color: #0a1628;
    border-radius: 6px;
    padding: 8px;
}

.log-label {
    color: #a0a0b0;
    font-size: 10px;
}

.log-text {
    color: #a0a0b0;
    font-family: "Monospace", "Courier New", monospace;
    font-size: 10px;
}
"""


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _is_running() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _send_signal(sig: int) -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, OSError):
        return False


class JarvisGUI:
    def __init__(self, auto_launch: bool = True) -> None:
        self._is_on = False
        self._user_off = False  # track manual off
        self._jarvis_proc: subprocess.Popen | None = None
        self._threshold = 0.5
        self._log_lines: list[str] = []

        self._build_window()
        self._apply_css()

        if auto_launch:
            self._reset_switch_state()
            GLib.timeout_add(500, self._launch_jarvis)

        GLib.timeout_add(2000, self._poll_status)

    def _build_window(self) -> None:
        self._window = Gtk.Window(title="Jarvis Control")
        self._window.set_default_size(360, 450)
        self._window.set_resizable(False)
        self._window.set_keep_above(True)
        self._window.set_position(Gtk.WindowPosition.CENTER)
        self._window.connect("destroy", self._on_destroy)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_start(22)
        main_box.set_margin_end(22)
        main_box.set_margin_top(15)
        main_box.set_margin_bottom(15)
        main_box.get_style_context().add_class("window-bg")
        self._window.add(main_box)

        # --- Banner Image ---
        banner_path = JARVIS_ROOT / "jarvis-gui-banner.svg"
        if banner_path.exists():
            banner_img = Gtk.Image.new_from_file(str(banner_path))
            banner_img.set_halign(Gtk.Align.CENTER)
            banner_img.set_valign(Gtk.Align.CENTER)
            main_box.pack_start(banner_img, False, False, 0)
        else:
            # Fallback to text labels
            title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            title_box.set_margin_start(8)
            title_box.set_margin_end(8)
            main_box.pack_start(title_box, False, False, 0)
            title = Gtk.Label(label="J.A.R.V.I.S.")
            title.get_style_context().add_class("title-label")
            title.set_margin_top(8)
            title_box.pack_start(title, False, False, 0)
            version = Gtk.Label(label="v1.0")
            version.get_style_context().add_class("subtitle-label")
            version.set_halign(Gtk.Align.END)
            title_box.pack_end(version, False, False, 0)
            subtitle = Gtk.Label(label="Asistente de Voz Local")
            subtitle.get_style_context().add_class("subtitle-label")
            subtitle.set_margin_start(8)
            subtitle.set_margin_end(8)
            main_box.pack_start(subtitle, False, False, 0)

        # --- Status Card ---
        status_frame = Gtk.Frame()
        status_frame.get_style_context().add_class("status-card")
        main_box.pack_start(status_frame, False, False, 0)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_box.set_margin_start(10)
        status_box.set_margin_end(10)
        status_box.set_margin_top(10)
        status_box.set_margin_bottom(10)
        status_frame.add(status_box)

        self._status_label = Gtk.Label(label="● INACTIVO")
        self._status_label.get_style_context().add_class("status-inactive")
        status_box.pack_start(self._status_label, False, False, 0)

        self._status_detail = Gtk.Label(label="Esperando inicio...")
        self._status_detail.get_style_context().add_class("status-detail")
        status_box.pack_start(self._status_detail, False, False, 0)

        # --- Power Button ---
        self._power_btn = Gtk.Button(label="⏻ ENCENDER")
        self._power_btn.get_style_context().add_class("power-btn")
        self._power_btn.set_margin_start(20)
        self._power_btn.set_margin_end(20)
        self._power_btn.connect("clicked", self._on_power_clicked)
        main_box.pack_start(self._power_btn, False, False, 8)

        # --- Sensitivity Slider ---
        slider_frame = Gtk.Frame()
        slider_frame.get_style_context().add_class("slider-card")
        main_box.pack_start(slider_frame, False, False, 0)

        slider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        slider_box.set_margin_start(10)
        slider_box.set_margin_end(10)
        slider_box.set_margin_top(8)
        slider_box.set_margin_bottom(8)
        slider_frame.add(slider_box)

        slider_title = Gtk.Label(label="Sensibilidad Wake Word")
        slider_title.get_style_context().add_class("slider-label")
        slider_box.pack_start(slider_title, False, False, 0)

        slider_hint = Gtk.Label(label="Baja ← → Alta")
        slider_hint.get_style_context().add_class("slider-hint")
        slider_box.pack_start(slider_hint, False, False, 0)

        self._slider_value_label = Gtk.Label(label="0.50")
        self._slider_value_label.get_style_context().add_class("slider-value")
        slider_box.pack_start(self._slider_value_label, False, False, 0)

        self._slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 0.9, 0.05)
        self._slider.set_value(0.5)
        self._slider.connect("value-changed", self._on_slider_changed)
        slider_box.pack_start(self._slider, False, False, 0)

        # --- LLM Provider Selector ---
        provider_frame = Gtk.Frame()
        provider_frame.get_style_context().add_class("provider-card")
        main_box.pack_start(provider_frame, False, False, 0)

        provider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        provider_box.set_margin_start(10)
        provider_box.set_margin_end(10)
        provider_box.set_margin_top(8)
        provider_box.set_margin_bottom(8)
        provider_frame.add(provider_box)

        provider_title = Gtk.Label(label="IA Provider")
        provider_title.get_style_context().add_class("provider-label")
        provider_box.pack_start(provider_title, False, False, 0)

        provider_hint = Gtk.Label(label="Seleccioná dónde procesar las órdenes")
        provider_hint.get_style_context().add_class("provider-hint")
        provider_box.pack_start(provider_hint, False, False, 0)

        # --- Segmented pill selector ---
        pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        pill_box.get_style_context().add_class("provider-pill-box")
        pill_box.set_halign(Gtk.Align.CENTER)
        provider_box.pack_start(pill_box, False, False, 0)

        self._provider_buttons: dict[str, Gtk.RadioButton] = {}
        self._provider_labels: dict[str, Gtk.Label] = {}
        first_btn = None
        for pid, icon, text in [
            ("local", "🏠", "Local"),
            ("gemini", "☁️", "Gemini"),
            ("auto", "🔄", "Auto"),
        ]:
            btn = Gtk.RadioButton.new_with_label_from_widget(first_btn, f"{icon} {text}")
            if first_btn is None:
                first_btn = btn
            btn._provider_id = pid  # attach ID for handler
            btn.get_style_context().add_class("provider-pill")
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("toggled", self._on_provider_toggled)
            pill_box.pack_start(btn, True, True, 0)
            self._provider_buttons[pid] = btn

        # Status label for active provider
        self._provider_status = Gtk.Label()
        self._provider_status.get_style_context().add_class("provider-active")
        provider_box.pack_start(self._provider_status, False, False, 0)

        # Load saved provider preference
        self._load_provider_preference()

        # --- Buttons Row ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_margin_start(8)
        btn_box.set_margin_end(8)
        main_box.pack_start(btn_box, False, False, 0)

        docs_btn = Gtk.Button(label="📖 Comandos")
        docs_btn.get_style_context().add_class("btn-secondary")
        docs_btn.connect("clicked", self._on_docs_clicked)
        btn_box.pack_start(docs_btn, True, True, 0)

        logs_btn = Gtk.Button(label="📋 Logs")
        logs_btn.get_style_context().add_class("btn-secondary")
        logs_btn.connect("clicked", self._on_logs_clicked)
        btn_box.pack_start(logs_btn, True, True, 0)

        # --- Log Preview ---
        log_frame = Gtk.Frame()
        log_frame.get_style_context().add_class("log-card")
        main_box.pack_start(log_frame, True, True, 0)

        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        log_box.set_margin_top(6)
        log_box.set_margin_bottom(6)
        log_box.set_margin_start(12)
        log_box.set_margin_end(12)
        log_frame.add(log_box)

        log_title = Gtk.Label(label="Actividad reciente")
        log_title.get_style_context().add_class("log-label")
        log_title.set_halign(Gtk.Align.START)
        log_box.pack_start(log_title, False, False, 0)

        self._log_view = Gtk.TextView()
        self._log_view.get_style_context().add_class("log-text")
        self._log_view.set_editable(False)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._log_view.set_left_margin(4)
        self._log_view.set_right_margin(4)
        self._log_view.set_top_margin(4)
        self._log_view.set_bottom_margin(4)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(80)
        scroll.add(self._log_view)
        log_box.pack_start(scroll, True, True, 0)

    def _apply_css(self) -> None:
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _on_power_clicked(self, button) -> None:
        if self._is_on:
            self._stop_jarvis()
            self._user_off = True
        else:
            self._user_off = False
            self._reset_switch_state()
            self._launch_jarvis()

    def _reset_switch_state(self) -> None:
        """Reset switched_off to false so MicSwitch opens the mic."""
        try:
            state = {}
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text())
            state["switched_off"] = False
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _launch_jarvis(self) -> bool:
        import subprocess as _sp
        import time as _t
        if _is_running():
            # Kill stale process tree and start fresh
            self._log("Matando procesos Jarvis viejos...")
            # Kill our subprocess group
            if self._jarvis_proc and self._jarvis_proc.poll() is None:
                try:
                    os.killpg(os.getpgid(self._jarvis_proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
            # Kill by PID file
            pid = _read_pid()
            if pid is not None:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
            # Force-kill children
            _sp.run(["pkill", "-9", "-f", "whisper-cli"], capture_output=True, timeout=3)
            _sp.run(["pkill", "-9", "-f", "gst-launch-1.0"], capture_output=True, timeout=3)
            _t.sleep(1)

        # Ensure state is clean before launching
        self._reset_switch_state()

        # Read LLM provider preference from state.json
        llm_provider = "local"
        try:
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text())
                llm_provider = state.get("llm_provider", "local")
        except Exception:
            pass

        # Read Gemini API key from .env if present
        gemini_key = ""
        try:
            env_file = JARVIS_ROOT / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                        gemini_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

        self._log("Iniciando Jarvis...")
        self._status_detail.set_text("Iniciando...")

        try:
            env = os.environ.copy()
            env["JARVIS_LLM_PROVIDER"] = llm_provider
            if gemini_key:
                env["GEMINI_API_KEY"] = gemini_key
            self._jarvis_proc = subprocess.Popen(
                [str(VENV_PY), "-m", "jarvis", "start"],
                cwd=str(JARVIS_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                preexec_fn=os.setsid,  # own process group for clean tree kill
            )
            self._is_on = True
            self._log(f"Jarvis PID: {self._jarvis_proc.pid}")
            self._update_ui()
            threading.Thread(target=self._read_output, daemon=True).start()
        except Exception as e:
            self._log(f"Error al iniciar: {e}")
            self._status_detail.set_text(f"Error: {e}")

        return False  # don't repeat timer

    def _stop_jarvis(self) -> None:
        """Kill Jarvis subprocess and ALL its children (whisper-cli, gst, etc.)."""
        import subprocess as _sp
        import time as _t
        killed = False

        # 1. Kill the process group of our direct subprocess (catches all children)
        if self._jarvis_proc and self._jarvis_proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._jarvis_proc.pid), signal.SIGTERM)
                killed = True
            except (ProcessLookupError, OSError):
                pass

        # 2. Kill by PID file (in case process was adopted or we don't own it)
        pid = _read_pid()
        if pid is not None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                killed = True
            except (ProcessLookupError, OSError):
                pass

        # 3. Wait briefly, then force-kill stragglers (only whisper-cli, NOT jarvis_gui)
        _t.sleep(0.5)
        _sp.run(["pkill", "-9", "-f", "whisper-cli"], capture_output=True, timeout=3)
        _sp.run(["pkill", "-9", "-f", "gst-launch-1.0"], capture_output=True, timeout=3)

        if killed:
            self._log("Jarvis + hijos terminados")
        else:
            self._log("No había procesos Jarvis activos")
        self._is_on = False
        self._update_ui()

    def _read_output(self) -> None:
        if self._jarvis_proc and self._jarvis_proc.stdout:
            for line in self._jarvis_proc.stdout:
                line = line.strip()
                if line:
                    GLib.idle_add(self._log, line)
                    # Update status when Jarvis announces readiness
                    if "listo" in line.lower() or "jarvis" in line.lower():
                        GLib.idle_add(self._status_detail.set_text, "Escuchando 'JARVIS'...")

    def _on_slider_changed(self, scale) -> None:
        self._threshold = scale.get_value()
        self._slider_value_label.set_text(f"{self._threshold:.2f}")
        self._apply_threshold()

    def _apply_threshold(self) -> None:
        try:
            state = {}
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text())
            state["wake_threshold"] = self._threshold
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, indent=2))
            self._log(f"Sensibilidad: {self._threshold:.2f}")
        except Exception as e:
            self._log(f"Error umbral: {e}")

    def _load_provider_preference(self) -> None:
        """Load saved LLM provider preference from state.json."""
        saved = "local"
        try:
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text())
                saved = state.get("llm_provider", "local")
        except Exception:
            pass
        self._set_provider(saved, from_load=True)

    def _on_provider_toggled(self, button) -> None:
        """Handle pill toggle — only react to the button being activated."""
        if not button.get_active():
            return
        pid = getattr(button, "_provider_id", None)
        if pid is None:
            return
        self._set_provider(pid)

    def _set_provider(self, pid: str, *, from_load: bool = False) -> None:
        """Update UI, CSS classes, and persist selection."""
        # Update radio button states
        for key, btn in self._provider_buttons.items():
            btn.handler_block_by_func(self._on_provider_toggled)
            btn.set_active(key == pid)
            btn.handler_unblock_by_func(self._on_provider_toggled)
            # Swap CSS class: active vs inactive
            ctx = btn.get_style_context()
            ctx.remove_class("provider-pill")
            ctx.remove_class("provider-pill-active")
            ctx.add_class("provider-pill-active" if key == pid else "provider-pill")

        # Update status label
        self._update_provider_status(pid)

        # Persist (skip on initial load to avoid redundant write)
        if not from_load:
            try:
                state = {}
                if STATE_FILE.exists():
                    state = json.loads(STATE_FILE.read_text())
                state["llm_provider"] = pid
                STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                STATE_FILE.write_text(json.dumps(state, indent=2))
                self._log(f"IA Provider: {pid}")
            except Exception as e:
                self._log(f"Error provider: {e}")

    def _update_provider_status(self, provider: str) -> None:
        """Update the provider status label."""
        labels = {
            "local": "🏠 Solo IA local (sin conexión)",
            "gemini": "☁️ Gemini (nube — requiere API key)",
            "auto": "🔄 Auto (Gemini primero, fallback local)",
        }
        self._provider_status.set_text(labels.get(provider, provider))

    def _update_ui(self) -> None:
        if self._is_on:
            self._status_label.set_text("● ACTIVO")
            self._status_label.get_style_context().remove_class("status-inactive")
            self._status_label.get_style_context().add_class("status-active")
            self._status_detail.set_text("Iniciando...")
            self._power_btn.set_label("⏻ APAGAR")
            self._power_btn.get_style_context().remove_class("power-btn")
            self._power_btn.get_style_context().add_class("power-btn-off")
        else:
            self._status_label.set_text("● INACTIVO")
            self._status_label.get_style_context().remove_class("status-active")
            self._status_label.get_style_context().add_class("status-inactive")
            self._status_detail.set_text("Detenido")
            self._power_btn.set_label("⏻ ENCENDER")
            self._power_btn.get_style_context().remove_class("power-btn-off")
            self._power_btn.get_style_context().add_class("power-btn")

    def _poll_status(self) -> bool:
        running = _is_running()
        if self._user_off:
            # User manually turned off — keep showing inactive even if process alive
            if self._is_on:
                self._is_on = False
                self._update_ui()
        else:
            if running != self._is_on:
                self._is_on = running
                self._update_ui()
        # Read FSM state for real-time status display
        if running:
            self._update_fsm_display()
        return True  # keep polling

    def _update_fsm_display(self) -> None:
        """Read FSM state file and update status labels."""
        try:
            if not FSM_STATE_FILE.exists():
                return
            raw = FSM_STATE_FILE.read_text().strip()
            if ":" not in raw:
                return
            state, detail = raw.split(":", 1)
            state = state.strip()
            label_text, detail_text, css_class = _FSM_LABELS.get(
                state, ("● ACTIVO", "", "status-active")
            )
            # Append detail (transcript or intent) if present
            if detail:
                label_text = f"{label_text}: {detail[:40]}"
            self._status_label.set_text(label_text)
            self._status_label.get_style_context().remove_class("status-active")
            self._status_label.get_style_context().remove_class("status-inactive")
            self._status_label.get_style_context().add_class(css_class)
            if detail_text:
                self._status_detail.set_text(detail_text)
        except Exception:
            pass  # best-effort — never crash the GUI

    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self._log_lines.append(line)
        if len(self._log_lines) > 50:
            self._log_lines = self._log_lines[-50:]
        buf = self._log_view.get_buffer()
        end_iter = buf.get_end_iter()
        buf.insert(end_iter, line)
        # Auto-scroll
        end_iter = buf.get_end_iter()
        self._log_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)

    def _on_destroy(self, widget) -> None:
        """Kill jarvis subprocess tree before closing the GUI."""
        import subprocess as _sp
        # Kill process group of our direct subprocess
        if self._jarvis_proc and self._jarvis_proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._jarvis_proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        # Kill by PID file
        pid = _read_pid()
        if pid is not None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        # Force-kill children
        _sp.run(["pkill", "-9", "-f", "whisper-cli"], capture_output=True, timeout=3)
        _sp.run(["pkill", "-9", "-f", "gst-launch-1.0"], capture_output=True, timeout=3)
        Gtk.main_quit()

    def _on_docs_clicked(self, button) -> None:
        doc_win = Gtk.Window(title="Jarvis — Manual de Comandos")
        doc_win.set_default_size(550, 450)
        doc_win.set_keep_above(True)

        docs_content = ""
        if DOCS_FILE.exists():
            docs_content = DOCS_FILE.read_text()
        else:
            docs_content = self._get_builtin_docs()

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_left_margin(10)
        text_view.set_right_margin(10)
        text_view.set_top_margin(10)
        text_view.set_bottom_margin(10)
        text_view.get_style_context().add_class("log-text")

        buf = text_view.get_buffer()
        buf.set_text(docs_content)

        scroll = Gtk.ScrolledWindow()
        scroll.add(text_view)
        doc_win.add(scroll)
        doc_win.show_all()

    def _on_logs_clicked(self, button) -> None:
        log_win = Gtk.Window(title="Jarvis — Logs")
        log_win.set_default_size(550, 400)
        log_win.set_keep_above(True)

        logs_dir = Path.home() / ".local" / "state" / "jarvis" / "logs"
        content = ""
        if logs_dir.exists():
            for f in sorted(logs_dir.glob("*.log"), reverse=True)[:5]:
                content += f"=== {f.name} ===\n{f.read_text()[:3000]}\n\n"
        if not content:
            content = "No hay logs disponibles.\nLos logs se generan cuando Jarvis procesa comandos."

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_left_margin(10)
        text_view.set_right_margin(10)
        text_view.get_style_context().add_class("log-text")

        buf = text_view.get_buffer()
        buf.set_text(content)

        scroll = Gtk.ScrolledWindow()
        scroll.add(text_view)
        log_win.add(scroll)
        log_win.show_all()

    def _get_builtin_docs(self) -> str:
        return """═══════════════════════════════════════════════
  J.A.R.V.I.S. — Manual de Comandos
═══════════════════════════════════════════════

COMANDOS DE VOZ
════════════════

Decí "JARVIS" para activarlo, y luego tu comando.

COMANDOS DISPONIBLES:
─────────────────────

  📂 SISTEMA
  • "abrí la terminal"
  • "abrí firefox"
  • "cerrá firefox"

  📁 ARCHIVOS
  • "creá una carpeta llamada [nombre]"
  • "borrá el archivo [nombre]"

  🌐 WEB
  • "buscá [término] en internet"
  • "abrí [sitio web]"

  💻 DESARROLLO
  • "mostrá el estado del proyecto"
  • "creá un commit con mensaje [texto]"

  🗣️ ASISTENTE
  • "¿Qué podés hacer?"
  • "apagá"

═══════════════════════════════════════════════

CONTROLES DEL PANEL
════════════════════

  ⏻ Botón ON/OFF — Enciende o apaga Jarvis
  🎚️ Slider — Controla sensibilidad del wake word
  📖 Comandos — Muestra esta ventana
  📋 Logs — Muestra logs de actividad

═══════════════════════════════════════════════
"""

    def run(self) -> None:
        self._window.show_all()
        Gtk.main()


def main():
    parser = argparse.ArgumentParser(description="Jarvis GUI")
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="No lanzar Jarvis (ya está corriendo)",
    )
    args = parser.parse_args()

    app = JarvisGUI(auto_launch=not args.no_launch)
    app.run()


if __name__ == "__main__":
    main()
