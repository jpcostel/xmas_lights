#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3
import board
import neopixel

SPINES = 1
RINGS = 10
PIXELS_PER_SPINE = 50

# total pixels in entire tree
NUM_PIXELS = SPINES * PIXELS_PER_SPINE

pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, auto_write=False, brightness=0.5)

def pixel_index(spine, ring):
    """
    returns actual LED index based on spine & ring index.
    ring 0 = top
    ring RINGS-1 = bottom
    """
    if spine % 2 == 0:
        # even -> runs top down
        return spine * PIXELS_PER_SPINE + ring
    else:
        # odd -> runs bottom up
        return spine * PIXELS_PER_SPINE + (PIXELS_PER_SPINE - ring - 1)

def set_pixel(spine, ring, color):
    idx = pixel_index(spine, ring)
    pixels[idx] = color

def clear():
    for i in range(NUM_PIXELS):
        pixels[i] = (0,0,0)
    pixels.show()

def fifo(pixels, gap=2, offset=0, color=(0,0,255), sleep=0.1):
    pixels.fill((0,0,0))
    gap = gap + 1
    for i in range(pixels.n):
        if (i+offset) % gap == 0:
            pixels[i] = color
    pixels.show()

# example test pattern
while True:
    for g in gaps:
        for i in range(50):
            fifo(pixels, gap=g, offset=i)
            time.sleep(0.1)
 

