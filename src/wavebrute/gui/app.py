"""Neo-brutalist Kivy GUI with light/dark theme support.

WaveBruteApp provides a ScreenManager with four functional screens,
a persistent header containing a theme toggle, and dynamic color
palettes that preserve thick borders, hard shadows and chunky buttons.
Dark variant uses near-black background with neon pink/lime/yellow
accents for screaming brutalist contrast.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

from ..auditor import Auditor
from .screens import (
    ScanScreen,
    AttackScreen,
    CaptureScreen,
    ReportScreen,
    BrutalistButton,
    BrutalistLabel,
)


class WaveBruteApp(App):
    """Main Kivy application with theme support."""

    def __init__(self, simulation_mode: bool = True, dark_theme: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.simulation_mode = simulation_mode
        self.dark_theme = dark_theme
        self.auditor = Auditor(simulation_mode=simulation_mode)
        self.colors = self._load_theme_colors()
        Window.clearcolor = self.colors["background"]

    def _load_theme_colors(self):
        """Return color palette for current theme while preserving brutalist contrast."""
        if self.dark_theme:
            return {
                "background": get_color_from_hex("#111111"),
                "foreground": get_color_from_hex("#f0f0f0"),
                "accent": get_color_from_hex("#ff004d"),
                "lime": get_color_from_hex("#00ff9f"),
                "yellow": get_color_from_hex("#ffff00"),
                "border": get_color_from_hex("#ffff00"),
                "button_bg": get_color_from_hex("#1f1f1f"),
                "shadow": get_color_from_hex("#000000"),
            }
        return {
            "background": get_color_from_hex("#f4f0e8"),
            "foreground": get_color_from_hex("#111111"),
            "accent": get_color_from_hex("#ff004d"),
            "lime": get_color_from_hex("#00b36b"),
            "yellow": get_color_from_hex("#e6b800"),
            "border": get_color_from_hex("#111111"),
            "button_bg": get_color_from_hex("#ffffff"),
            "shadow": get_color_from_hex("#555555"),
        }

    def toggle_dark_theme(self, *_args):
        """Toggle dark theme and refresh all UI elements."""
        self.dark_theme = not self.dark_theme
        self.colors = self._load_theme_colors()
        Window.clearcolor = self.colors["background"]

        if hasattr(self, "toggle_btn"):
            self.toggle_btn.text = "LIGHT" if self.dark_theme else "DARK"
            self.toggle_btn.update_style()

        if hasattr(self, "header_title"):
            self.header_title.color = self.colors["accent"]
            self.header_title.update_style()

        # Refresh every screen
        if hasattr(self, "sm") and self.sm:
            for screen in self.sm.screens:
                if hasattr(screen, "update_theme"):
                    screen.update_theme()

    def build(self):
        """Build UI with persistent brutalist header + ScreenManager."""
        self.sm = ScreenManager()

        self.sm.add_widget(
            ScanScreen(name="scan", auditor=self.auditor, app=self)
        )
        self.sm.add_widget(
            AttackScreen(name="attack", auditor=self.auditor, app=self)
        )
        self.sm.add_widget(
            CaptureScreen(name="capture", auditor=self.auditor, app=self)
        )
        self.sm.add_widget(
            ReportScreen(name="report", auditor=self.auditor, app=self)
        )

        root = BoxLayout(orientation="vertical")

        # Brutalist header
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(74),
            padding=dp(12),
            spacing=dp(16),
        )
        with header.canvas.before:
            from kivy.graphics import Color, Line
            Color(*self.colors["border"])
            Line(width=dp(4), rectangle=(header.x, header.y, header.width, header.height))

        self.header_title = BrutalistLabel(
            text="WAVEBRUTE",
            font_size=dp(34),
            bold=True,
            color=self.colors["accent"],
            app=self,
            size_hint_x=0.65,
        )
        self.toggle_btn = BrutalistButton(
            text="DARK" if not self.dark_theme else "LIGHT",
            font_size=dp(18),
            size_hint_x=0.35,
            app=self,
            on_press=self.toggle_dark_theme,
        )
        header.add_widget(self.header_title)
        header.add_widget(self.toggle_btn)

        root.add_widget(header)
        root.add_widget(self.sm)

        self.header = header
        return root


if __name__ == "__main__":
    WaveBruteApp().run()
