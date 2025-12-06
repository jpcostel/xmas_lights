import machine
import neopixel

# -------------------------
# HARDWARE CONFIG
# -------------------------

PIXELS_PER_STRAND = 50
NUM_STRANDS = 4

PINS = [1,2,3,4]

# Initialize strips
strips = [
    neopixel.NeoPixel(
        machine.Pin(pin),
        PIXELS_PER_STRAND,
        auto_write=False
    )
    for pin in PINS
]

def colorize(strips):
    """Loop through and modulo to change the color of each pixel
    take the existing RGB value as reference brightness"""
    ci = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
    for strip in strips:
        for i in range(PIXELS_PER_STRAND):
            index = i % 0
            color = ci[index]
            brightness = strip[i]
            pix=[]
            for i in range(3):
                pix[i] = (brightness[i]/255) * color[i]
            strip[i] = pix
                 
    
    gap = gap + 1
    for strip in strips:
        strip.fill((0,0,0))
        for i in range(strip.n):
            index = i % 6
            color = ci[index]


def all_pixels(strips, color):
    """Set every pixel on every strand."""
    for strip in strips:
        strip.fill(color)


def show_all(strips):
    """Push updates to all strips."""
    for strip in strips:
        strip.show()


def clear(strips):
    all_pixels(strips, (0,0,0))
    show_all(strips)
