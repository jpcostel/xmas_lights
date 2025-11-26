#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3
import board
import neopixel
import time
import argparse
import wiring 
import pulse


# total pixels in entire tree
PIX_PER_LINE = 50

pixels1 = neopixel.NeoPixel(board.D18, PIX_PER_LINE, auto_write=False, brightness=0.5)
pixels2 = neopixel.NeoPixel(board.D19, PIX_PER_LINE, auto_write=False, brightness=0.5)

def pixel_index(spine, ring):
    """
    returns actual LED index based on spine & ring index.
    ring 0 = top
    ring RINGS-1 = bottom
    """
    if spine % 2 == 0:
        # even -> runs top down
        return spine * PIX_PER_LINE + ring
    else:
        # odd -> runs bottom up
        return spine * PIX_PER_LINE + (PIX_PER_LINE - ring - 1)

def set_pixel(spine, ring, color):
    idx = pixel_index(spine, ring)
    pixels[idx] = color

def clear():
    for i in range(NUM_PIXELS):
        pixels[i] = (0,0,0)
    pixels.show()

def fifo(pixels, gap=2, offset=0, color=(0,0,255), sleep=0.1):
    ci = ((255,255,0), (0,0,255), (255,0,0), (0,255,0), (0,255,255), (255,0,255))
    pixels.fill((0,0,0))
    gap = gap + 1
    for i in range(pixels.n):
        index = i % 6
        color = ci[index]
        if (i+offset) % gap == 0:
            pixels[i] = color
    pixels.show()

def parse_args():
    """
    Parse binary command-line options:
    --twinkle
    --pulse
    --xmas
    --xmas_twinkle

    Returns an argparse.Namespace with Boolean fields.
    """

    parser = argparse.ArgumentParser(
        description="LED Effects Controller"
    )

    parser.add_argument(
        "--twinkle",
        action="store_true",
        help="Enable twinkle effect", 
        default=True
    )

    parser.add_argument(
        "--pulse",
        action="store_true",
        help="Enable global pulse effect", 
        default=False
    )

    parser.add_argument(
        "--xmas",
        action="store_true",
        help="Enable Xmas animation", 
        default=False
    )

    parser.add_argument(
        "--xmas_twinkle",
        action="store_true",
        help="Enable Xmas-style twinkling",
        default=False
    )

    # Parse and return
    return parser.parse_args()


def main():
    # example test pattern
    args = parse_args()
    try:
        if args.twinkle:
            pulse.twinkle_stars(150)
        elif args.pulse:
            pulse.pulse_all()
        elif args.xmas:
            gaps = (2,3,4,5,10,15,25,35,45)
            while True:
                for g in gaps:
                    for i in range(20):
                        fifo(pixels1, gap=g, offset=i)
                        fifo(pixels2, gap=g, offset=i)
                        time.sleep(0.15)
        elif args.xmas_twinkle:
            pulse.xmas_twinkle()
            

    except KeyboardInterrupt:
        print("\n👋 Exiting")
        pixels1.fill((0,0,0))
        pixels2.fill((0,0,0))
        pixels1.show()
        pixels2.show()

if __name__ == '__main__':
    main()