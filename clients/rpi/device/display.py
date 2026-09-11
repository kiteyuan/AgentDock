"""OLED / console display."""

from __future__ import annotations

from loguru import logger

from device.state import DeviceState


class Display:
    def show(self, state: DeviceState, line: str = "") -> None:
        raise NotImplementedError


class ConsoleDisplay(Display):
    def show(self, state: DeviceState, line: str = "") -> None:
        extra = f" | {line}" if line else ""
        print(f"[OLED] AgentDock  ● {state.value}{extra}")


class SSD1306Display(Display):
    """Requires luma.oled + physical SSD1306."""

    def __init__(self, port: int = 1, address: int = 0x3C, width: int = 128, height: int = 64) -> None:
        from luma.core.interface.serial import i2c
        from luma.oled.device import ssd1306
        from PIL import Image, ImageDraw, ImageFont

        serial = i2c(port=port, address=address)
        self.device = ssd1306(serial, width=width, height=height)
        self._Image = Image
        self._ImageDraw = ImageDraw
        self._font = ImageFont.load_default()

    def show(self, state: DeviceState, line: str = "") -> None:
        img = self._Image.new("1", (self.device.width, self.device.height))
        draw = self._ImageDraw.Draw(img)
        draw.text((0, 0), "AgentDock", font=self._font, fill=255)
        draw.text((0, 16), f"* {state.value}", font=self._font, fill=255)
        if line:
            draw.text((0, 36), line[:21], font=self._font, fill=255)
        self.device.display(img)


def build_display(cfg: dict) -> Display:
    if not cfg.get("enabled", True):
        return ConsoleDisplay()
    driver = cfg.get("driver", "console")
    if driver == "ssd1306":
        try:
            return SSD1306Display(
                port=int(cfg.get("i2c_port", 1)),
                address=int(cfg.get("i2c_address", 0x3C)),
                width=int(cfg.get("width", 128)),
                height=int(cfg.get("height", 64)),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OLED init failed ({}), fallback console", exc)
    return ConsoleDisplay()
