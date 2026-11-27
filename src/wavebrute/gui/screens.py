"""Kivy screens and brutalist widgets for WaveBrute.

All widgets pull colors from the App instance and support runtime
theme switching while keeping 4px thick borders and 6dp hard shadows.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.metrics import dp
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import ObjectProperty
from kivy.utils import get_color_from_hex

from ..auditor import Auditor


class BrutalistLabel(Label):
    """Neo-brutalist label with thick border support and theme awareness."""

    app = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.app = kwargs.pop("app", None)
        super().__init__(**kwargs)
        self.color = get_color_from_hex("#111111")
        self.update_style()

    def update_style(self):
        """Redraw border and apply current theme colors."""
        if not self.app or not self.canvas:
            return
        colors = self.app.colors
        self.color = colors["foreground"]

        self.canvas.before.clear()
        with self.canvas.before:
            Color(*colors["border"])
            Line(width=dp(3.5), rectangle=(self.x, self.y, self.width, self.height))


class BrutalistButton(Button):
    """Chunky neo-brutalist button with hard shadow and thick border."""

    app = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.app = kwargs.pop("app", None)
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.color = get_color_from_hex("#ffffff")
        self.size_hint_y = None
        self.height = dp(68)
        self.font_size = dp(18)
        self.update_style()
        self.bind(pos=self.update_rects, size=self.update_rects)

    def update_style(self):
        """Rebuild canvas with current theme (bg, border, shadow)."""
        if not self.app or not self.canvas:
            return
        colors = self.app.colors
        self.color = colors["foreground"]
        self.canvas.before.clear()
        with self.canvas.before:
            # shadow (hard offset)
            Color(*colors["shadow"], 0.65)
            Rectangle(pos=(self.x + dp(6), self.y - dp(6)), size=self.size)
            # button background
            Color(*colors["button_bg"])
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            # thick border
            Color(*colors["border"])
            self.border_line = Line(
                width=dp(4),
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(4)),
            )

    def update_rects(self, *_args):
        if hasattr(self, "bg_rect"):
            self.bg_rect.pos = self.pos
            self.bg_rect.size = self.size
        if hasattr(self, "border_line"):
            self.border_line.rounded_rectangle = (
                self.x,
                self.y,
                self.width,
                self.height,
                dp(4),
            )


class BaseScreen(Screen):
    """Common base for all screens with theme refresh capability."""

    auditor = ObjectProperty()
    app = ObjectProperty()

    def __init__(self, auditor: Auditor = None, app=None, **kwargs):
        super().__init__(**kwargs)
        self.auditor = auditor
        self.app = app
        self.layout = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        self.add_widget(self.layout)

    def update_theme(self):
        """Walk children and update any Brutalist widgets."""
        def walk(widget):
            if isinstance(widget, (BrutalistButton, BrutalistLabel)):
                widget.update_style()
            for child in getattr(widget, "children", []):
                walk(child)
        walk(self)
        if self.app:
            self.layout.canvas.before.clear()
            with self.layout.canvas.before:
                from kivy.graphics import Color
                Color(*self.app.colors["background"])
                Rectangle(pos=self.layout.pos, size=self.layout.size)

    def on_pre_enter(self):
        if self.app:
            self.update_theme()


class ScanScreen(BaseScreen):
    """Screen for network scanning."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        title = BrutalistLabel(
            text="[ SCAN NETWORKS ]", font_size=dp(32), bold=True, app=self.app
        )
        scan_btn = BrutalistButton(
            text="SCAN (SIMULATION)",
            app=self.app,
            on_press=self.do_scan,
        )
        self.result_label = BrutalistLabel(
            text="Ready to scan. Press button above.",
            app=self.app,
            size_hint_y=None,
            height=dp(120),
        )
        self.layout.add_widget(title)
        self.layout.add_widget(scan_btn)
        self.layout.add_widget(self.result_label)

    def do_scan(self, *_args):
        if not self.auditor:
            return
        networks = self.auditor.scan()
        self.result_label.text = (
            f"Found {len(networks)} networks (simulation).\n"
            f"SSID examples: {', '.join(n.get('ssid','?') for n in networks[:2])}"
        )


class AttackScreen(BaseScreen):
    """Screen for attack / PMKID simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        title = BrutalistLabel(
            text="[ ATTACK / PMKID ]", font_size=dp(32), bold=True, app=self.app
        )
        attack_btn = BrutalistButton(
            text="SIMULATE BRUTE FORCE",
            app=self.app,
            on_press=self.sim_attack,
        )
        pmkid_btn = BrutalistButton(
            text="SIMULATE PMKID ATTACK",
            app=self.app,
            on_press=self.sim_pmkid,
        )
        self.result_label = BrutalistLabel(
            text="Press a button to run simulation.",
            app=self.app,
        )
        self.layout.add_widget(title)
        self.layout.add_widget(attack_btn)
        self.layout.add_widget(pmkid_btn)
        self.layout.add_widget(self.result_label)

    def sim_attack(self, *_args):
        if not self.auditor:
            return
        result = self.auditor.simulate_attack("Cafe_Rouge_FreeWiFi", max_attempts=6000)
        self.result_label.text = (
            f"Attack on Cafe_Rouge_FreeWiFi\n"
            f"Success: {result.get('success', False)}\n"
            f"Password: {result.get('password', 'N/A')}"
        )

    def sim_pmkid(self, *_args):
        if not self.auditor:
            return
        result = self.auditor.simulate_pmkid_attack("IoT-Devices")
        self.result_label.text = (
            f"PMKID on IoT-Devices\n"
            f"Success: {result.get('success', False)}\n"
            f"Notes: {result.get('notes', '')[:60]}..."
        )


class CaptureScreen(BaseScreen):
    """Screen for handshake capture upload and analysis."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        title = BrutalistLabel(
            text="[ CAPTURE ANALYSIS ]", font_size=dp(32), bold=True, app=self.app
        )
        upload_btn = BrutalistButton(
            text="UPLOAD .CAP / .PCAP",
            app=self.app,
            on_press=self.show_file_chooser,
        )
        self.result_label = BrutalistLabel(
            text="No capture loaded yet.",
            app=self.app,
            size_hint_y=None,
            height=dp(160),
        )
        self.layout.add_widget(title)
        self.layout.add_widget(upload_btn)
        self.layout.add_widget(self.result_label)

    def show_file_chooser(self, *_args):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        chooser = FileChooserListView(
            filters=["*.cap", "*.pcap", "*.pcapng"], size_hint_y=0.85
        )
        select_btn = BrutalistButton(
            text="ANALYZE SELECTED FILE",
            app=self.app,
            size_hint_y=None,
            height=dp(60),
            on_press=lambda x: self.analyze_file(chooser, popup),
        )
        content.add_widget(chooser)
        content.add_widget(select_btn)

        popup = Popup(title="Select Capture File", content=content, size_hint=(0.92, 0.85))
        popup.open()

    def analyze_file(self, chooser, popup):
        popup.dismiss()
        if not chooser.selection or not self.auditor:
            self.result_label.text = "No file selected."
            return
        try:
            analysis = self.auditor.analyze_handshake(chooser.selection[0])
            self.result_label.text = (
                f"File: {analysis.get('file','')}\n"
                f"Handshake: {analysis.get('has_handshake', False)}\n"
                f"Crack estimate: {analysis.get('crack_time_estimate','< 2 hours')}"
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.result_label.text = f"Analysis error: {exc}"


class ReportScreen(BaseScreen):
    """Screen for generating PDF/Markdown/HTML reports."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        title = BrutalistLabel(
            text="[ BUILD REPORT ]", font_size=dp(32), bold=True, app=self.app
        )
        pdf_btn = BrutalistButton(
            text="GENERATE PDF REPORT",
            app=self.app,
            on_press=self.generate_report,
        )
        self.result_label = BrutalistLabel(
            text="Report will be saved in current directory.",
            app=self.app,
        )
        self.layout.add_widget(title)
        self.layout.add_widget(pdf_btn)
        self.layout.add_widget(self.result_label)

    def generate_report(self, *_args):
        if not self.auditor:
            return
        try:
            path = self.auditor.build_report(title="WaveBrute Ethical Audit")
            self.result_label.text = f"Report saved successfully:\n{path}"
        except RuntimeError:
            # PDF export unavailable on this build (e.g. reportlab isn't
            # bundled in this APK) - fall back to an HTML report instead.
            try:
                path = self.auditor.build_report(title="WaveBrute Ethical Audit", format="html")
                self.result_label.text = f"PDF unavailable on this build - saved HTML report instead:\n{path}"
            except Exception as exc:  # pylint: disable=broad-except
                self.result_label.text = f"Report error: {exc}"
        except Exception as exc:  # pylint: disable=broad-except
            self.result_label.text = f"Report error: {exc}"


if __name__ == "__main__":
    # For quick widget testing
    from kivy.app import App as KivyApp
    from ..auditor import Auditor

    class TestApp(KivyApp):
        def build(self):
            auditor = Auditor(simulation_mode=True)
            screen = ScanScreen(auditor=auditor, app=self)
            self.dark_theme = False
            self.colors = {"background": (0.1, 0.1, 0.1, 1)}
            return screen

    TestApp().run()
