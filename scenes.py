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
    # New scenes go at the end: HomeKit accessory IDs follow this order, so
    # inserting above would renumber the existing scene switches.
    # The inline import lets these run even if the Pico hasn't been reset
    # since halloween.py was copied over (boot.py only runs at reset).
    "jack_classic": {
        "name": "Jack O Lantern",
        "web_label": "🎃 Jack-o'-Lantern",
        "cmd": "import halloween; halloween.jack_o_lantern(strips, 0)",
    },
    "jack_scary": {
        "name": "Scary Jack O Lantern",
        "web_label": "🎃 Scary Jack-o'-Lantern",
        "cmd": "import halloween; halloween.jack_o_lantern(strips, 1)",
    },
    "jack_happy": {
        "name": "Happy Jack O Lantern",
        "web_label": "🎃 Happy Jack-o'-Lantern",
        "cmd": "import halloween; halloween.jack_o_lantern(strips, 2)",
    },
    "jack_watching": {
        "name": "Watching Jack O Lantern",
        "web_label": "👀 Watching Jack-o'-Lantern",
        "cmd": "import halloween; halloween.watching_jack(strips, 0)",
    },
    "jack_watching_scary": {
        "name": "Scary Watching Jack O Lantern",
        "web_label": "👀 Scary Watching Jack-o'-Lantern",
        "cmd": "import halloween; halloween.watching_jack(strips, 1)",
    },
    "jack_watching_classic": {
        "name": "Classic Watching Jack O Lantern",
        "web_label": "👀 Classic Watching Jack-o'-Lantern",
        "cmd": "import halloween; halloween.watching_jack(strips, 2)",
    },
    "witch_moon": {
        "name": "Witch Moon",
        "web_label": "🌕 Witch Moon",
        "cmd": "import witch; witch.moon_witch(strips)",
    },
    "bat_swarm": {
        "name": "Bat Swarm",
        "web_label": "🦇 Bat Swarm",
        "cmd": "import bats; bats.bat_swarm(strips)",
    },
    "slime": {
        "name": "Dripping Slime",
        "web_label": "🟢 Dripping Slime",
        "cmd": "import drips; drips.drip(strips, 0)",
    },
    "blood": {
        "name": "Dripping Blood",
        "web_label": "🩸 Dripping Blood",
        "cmd": "import drips; drips.drip(strips, 1)",
    },
    "falling_leaves": {
        "name": "Falling Leaves",
        "web_label": "🍂 Falling Leaves",
        "cmd": "import leaves; leaves.falling_leaves(strips)",
    },
    "turkey": {
        "name": "Strutting Turkey",
        "web_label": "🦃 Strutting Turkey",
        "cmd": "import turkey; turkey.turkey(strips)",
    },
    "hearth_fire": {
        "name": "Hearth Fire",
        "web_label": "🔥 Hearth Fire",
        "cmd": "import fire; fire.hearth_fire(strips)",
    },
    "harvest_glow": {
        "name": "Harvest Glow",
        "web_label": "🌾 Harvest Glow",
        "cmd": "import harvest; harvest.harvest_glow(strips)",
    },
    "wheat_field": {
        "name": "Wheat Field",
        "web_label": "🌾 Wheat Field",
        "cmd": "import wheat; wheat.wheat_field(strips)",
    },
    "candlelight": {
        "name": "Candlelight",
        "web_label": "🕯️ Candlelight",
        "cmd": "import candles; candles.candlelight(strips)",
    },
    # Fed by weather_service.py on the Pi while it runs.
    "live_weather": {
        "name": "Live Weather",
        "web_label": "🌦️ Live Weather",
        "cmd": "import weather; weather.live_weather(strips)",
    },
}

DEFAULT_SCENE = "snow"
