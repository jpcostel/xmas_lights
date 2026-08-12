# scenes.py
#
# Single source of truth for the MicroPython commands sent to the Pico for
# each lighting scene. webserver.py (Flask UI) and homekit_bridge.py (HomeKit
# accessory) both import this so the two control surfaces can't drift apart.

SCENES = {
    "snow": {
        "name": "Snow",
        "web_label": "❄ Snow",
        "cmd": "snow.snowfall_effect(strips)",
    },
    "snow_colors": {
        "name": "Snow Xmas Colors",
        "web_label": "❄ Snow Xmas-Colors",
        "cmd": "snow.snowfall_effect(strips, True)",
    },
    "xmas_twinkle": {
        "name": "Xmas Twinkle Lights",
        "web_label": "✨ Xmas Twinkle Lights",
        "cmd": "stars.starfield(strips, ripples_on=False)",
    },
    "xmas_ripple": {
        "name": "Xmas With Ripples",
        "web_label": "✨ Xmas With Ripples",
        "cmd": "stars.starfield(strips)",
    },
    "gold_twinkle": {
        "name": "Gold Stars",
        "web_label": "✨ Gold Stars",
        "cmd": "stars.starfield(strips, 0, 1)",
    },
    "gold_ripple": {
        "name": "Gold Supernova",
        "web_label": "✨ Gold Supernova",
        "cmd": "stars.starfield(strips, 1, 1)",
    },
    "cool_twinkle": {
        "name": "Cool Stars",
        "web_label": "✨ Cool Stars",
        "cmd": "stars.starfield(strips, 0, 2)",
    },
    "cool_ripple": {
        "name": "Wavy Cool Stars",
        "web_label": "✨ Wavy Cool Stars",
        "cmd": "stars.starfield(strips, 1, 2)",
    },
    "warm_twinkle": {
        "name": "Hot Stars",
        "web_label": "✨ Hot Stars",
        "cmd": "stars.starfield(strips, 0, 3)",
    },
    "warm_ripple": {
        "name": "Explosive Hot Stars",
        "web_label": "✨ Explosive Hot Stars",
        "cmd": "stars.starfield(strips, 1, 3)",
    },
}

DEFAULT_SCENE = "snow"
