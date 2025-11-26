#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3
import board
import neopixel
import time
import argparse
import wiring 
import pulse


# -------------------------
# HARDWARE CONFIG
# -------------------------

strips = wiring.strips
PIXELS_PER_STRAND = wiring.PIXELS_PER_STRAND
NUM_STRANDS = wiring.NUM_STRANDS

# -------------------------
# UTILITY FUNCTIONS
# -------------------------

all_pixels = wiring.all_pixels
show_all = wiring.show_all
clear = wiring.clear



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
    clear(strips)
    args = parse_args()
    try:
        if args.xmas_twinkle:
            pulse.twinkle_stars(strips, 150)
        elif args.pulse:
            pulse.pulse_all(strips)
        elif args.xmas:
            gaps = (2,3,4,5,10,15,25,35,45)
            while True:
                time.sleep(5)
                for strip in strips:
                    for g in gaps:
                        for i in range(20):
                            fifo(strip, gap=g, offset=i)
        elif args.twinkle:
            # pulse.xmas_twinkle()
            pulse.twinkle_stars(strips, 150)


    except KeyboardInterrupt:
        print("\n👋 Exiting")
        clear(strips)

if __name__ == '__main__':
    main()