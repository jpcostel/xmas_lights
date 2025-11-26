#!/home/jpcostel/Projects/xmas_lights/.venv/bin/python3
import board
import neopixel
import time
import argparse
import wiring 
import effects


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
            effects.twinkle_stars(strips, 150)
        elif args.pulse:
            effects.pulse_all(strips)
        elif args.xmas:
            gaps = (2,3,5,8)
            while True:
                for strip in strips:
                    for g in gaps:
                        for i in range(20):
                            fifo(strip, gap=g, offset=i)
                            time.sleep(0.15)
        elif args.twinkle:
            # pulse.xmas_twinkle()
            effects.twinkle_stars(strips, 150)


    except KeyboardInterrupt:
        print("\n👋 Exiting")
        clear(strips)

if __name__ == '__main__':
    main()