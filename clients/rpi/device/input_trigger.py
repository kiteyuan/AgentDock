"""Talk trigger (click start / click stop): GPIO button or console Enter."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger


class Trigger:
    async def wait_press(self) -> None:
        raise NotImplementedError


class ConsoleTrigger(Trigger):
    async def wait_press(self) -> None:
        print("Enter: start/stop talk (Ctrl+C to quit)...")
        await asyncio.to_thread(sys.stdin.readline)


class GPIOTrigger(Trigger):
    def __init__(self, bcm: int, active_low: bool = True) -> None:
        self.bcm = bcm
        self.active_low = active_low
        try:
            from gpiozero import Button

            self._button = Button(bcm, pull_up=active_low)
        except Exception:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(bcm, GPIO.IN, pull_up_down=GPIO.PUD_UP if active_low else GPIO.PUD_DOWN)
            self._button = None
            self._gpio = GPIO

    async def wait_press(self) -> None:
        if self._button is not None:
            await asyncio.to_thread(self._button.wait_for_press)
            return
        GPIO = self._gpio
        target = GPIO.LOW if self.active_low else GPIO.HIGH
        while True:
            if GPIO.input(self.bcm) == target:
                await asyncio.sleep(0.05)
                return
            await asyncio.sleep(0.02)


def build_trigger(cfg: dict) -> Trigger:
    pin = cfg.get("gpio_bcm")
    if pin is None:
        return ConsoleTrigger()
    try:
        return GPIOTrigger(int(pin), active_low=bool(cfg.get("active_low", True)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("GPIO trigger failed ({}), using console Enter", exc)
        return ConsoleTrigger()
