#!/usr/bin/env python3
"""HomeKit bridge for the mantle lights.

Runs as its own long-lived process on the Raspberry Pi (alongside, not
instead of, webserver.py) and exposes the mantle NeoPixel strips as a
HomeKit bridge over the same pico_ctrl serial link the Flask UI uses:

  - "Mantle Lights": a Lightbulb accessory (On/Off + Brightness)
  - one Switch accessory per scene in scenes.py, acting as a radio-button
    scene picker ("Hey Siri, turn on Gold Stars")

State (on/off, brightness, active scene) is tracked in this process only.
It is NOT shared with webserver.py's Flask UI -- if you change scenes from
the web page, the Home app tiles won't update to reflect it until you next
change something from HomeKit.
"""
import logging
import signal

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_LIGHTBULB, CATEGORY_SWITCH

import pico_ctrl
from scenes import SCENES, DEFAULT_SCENE

logging.basicConfig(level=logging.INFO)

PERSIST_FILE = "homekit_state.json"
PORT = 51826


class MantleLights(Accessory):
    """Lightbulb: On/Off + Brightness for the mantle strands."""

    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, name):
        super().__init__(driver, name)

        serv_light = self.add_preload_service("Lightbulb", chars=["Brightness"])
        self.char_on = serv_light.configure_char("On", setter_callback=self._set_on)
        self.char_brightness = serv_light.configure_char(
            "Brightness", setter_callback=self._set_brightness
        )

        self.state = {"on": False, "brightness": 100, "scene": DEFAULT_SCENE}
        self.char_brightness.set_value(self.state["brightness"])

        # Filled in by build_bridge() once all scene switches exist, so this
        # accessory can keep them in sync (radio-button style).
        self.scene_switches = {}

    def _push_to_pico(self):
        cmd = SCENES[self.state["scene"]]["cmd"]
        brightness = self.state["brightness"] / 100.0
        pico_ctrl.interrupt()
        pico_ctrl.run(f"wiring.set_brightness({brightness:.2f})")
        pico_ctrl.run(cmd)

    def _set_on(self, value):
        if value:
            self.activate_scene(self.state["scene"])
        else:
            self.turn_off()

    def _set_brightness(self, value):
        self.state["brightness"] = value
        if self.state["on"]:
            self._push_to_pico()

    def activate_scene(self, key):
        """Switch the running effect, called directly or by a SceneSwitch."""
        self.state["scene"] = key
        self.state["on"] = True
        self.char_on.set_value(True, should_notify=True)
        for k, switch in self.scene_switches.items():
            switch.char_on.set_value(k == key, should_notify=True)
        self._push_to_pico()

    def turn_off(self):
        self.state["on"] = False
        self.char_on.set_value(False, should_notify=True)
        for switch in self.scene_switches.values():
            switch.char_on.set_value(False, should_notify=True)
        pico_ctrl.interrupt()
        pico_ctrl.run("wiring.clear(strips)")


class SceneSwitch(Accessory):
    """A single scene, exposed as a Switch. Turning it on activates the
    scene and turns off its siblings; turning off the active scene turns
    the lights off entirely."""

    category = CATEGORY_SWITCH

    def __init__(self, driver, name, key, lights):
        super().__init__(driver, name)
        self.key = key
        self.lights = lights

        serv_switch = self.add_preload_service("Switch")
        self.char_on = serv_switch.configure_char("On", setter_callback=self._set_on)

    def _set_on(self, value):
        if value:
            self.lights.activate_scene(self.key)
        elif self.lights.state.get("scene") == self.key:
            self.lights.turn_off()


def build_bridge(driver):
    bridge = Bridge(driver, "Mantle Lights Bridge")

    lights = MantleLights(driver, "Mantle Lights")
    bridge.add_accessory(lights)

    scene_switches = {}
    for key, scene in SCENES.items():
        switch = SceneSwitch(driver, scene["name"], key, lights)
        scene_switches[key] = switch
        bridge.add_accessory(switch)
    lights.scene_switches = scene_switches

    return bridge


def main():
    driver = AccessoryDriver(port=PORT, persist_file=PERSIST_FILE)
    driver.add_accessory(accessory=build_bridge(driver))
    signal.signal(signal.SIGTERM, driver.signal_handler)
    driver.start()


if __name__ == "__main__":
    main()
