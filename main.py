import time
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
from wiring import *
import snow

def main():
    # example test pattern
    clear(strips)
#    args = {xmas_twinkle=False}
#    try:
#        if args.xmas_twinkle:
#            effects.twinkle_stars(strips, 150)
#        elif args.pulse:
#            effects.pulse_all(strips)
#        elif args.xmas:
#            gaps = (2,3,5,8)
#            while True:
#                for g in gaps:
#                    for i in range(20):
#                        effects.blink(strips, gap=g, offset=i)
#                        time.sleep(0.15)
#        elif args.twinkle:
#            # pulse.xmas_twinkle()
#            effects.twinkle_stars(strips, 100)
    try:
        snow.snowfall_effect(strips)
        effects.twinkle_stars(strips, 75)

    except KeyboardInterrupt:
        print("\n👋 Exiting")
        clear(strips)

if __name__ == '__main__':
    main()