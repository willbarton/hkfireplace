import argparse
import asyncio
import logging
import random
import signal

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_LIGHTBULB
from pyhap.util import get_local_address
from pyhap.accessory_driver import AccessoryDriver

import board
import neopixel
import adafruit_fancyled.adafruit_fancyled as fancy

from colour import Color


logging.basicConfig(level=logging.DEBUG, format="[%(module)s] %(message)s")
logger = logging.getLogger(__name__)

# Color balance / brightness for gamma function
LEVELS = (0.9, 0.8, 0.15)

FIRE_COLORS = [
    # (0.75, 0.0, 0.2),  # NCS Red
    # (1.0, 0.0, 0.0),   # Red
    (0.7, 0.2, 0.0),  # Dark red
    (0.8, 0.3, 0.1),  # Orange
    (0.8, 0.4, 0.1),  # Orange
    (0.8, 0.6, 0.1),  # Orange
    (1.0, 0.5, 0.0),  # Orange
    (0.8, 0.6, 0.1),  # Yellow
    (1.0, 0.6, 0.2),  # Yellow
    (1.0, 0.8, 0.6),  # Bright yello
    # (0.9, 0.8, 1.0),  # Blueish
]

PURPLE_COLORS = [

]

BLUE_COLORS = [
    (0.2, 0.34, 0.83),
    (0.36, 0.52, 0.95),
    (0.5, 0.85, 0.98),
    (0.73, 0.97, 0.98),
    (0.9, 0.9, 1.0),
]

GREEN_COLORS = [

]

PRIDE_COLORS = [
    (0.52, 0.0, 0.49),
    (0.0, 0.0, 0.98),
    (0.0, 0.5, 0.09),
    (1.0, 1.0, 0.25),
    (1.0, 0.65, 0.17),
    (1.0, 0.0, 0.09),
]



class NeoPixelFlames(object):
    """
    Requires NeoPixel LEDs wired to the Raspberry Pi
    https://learn.adafruit.com/neopixels-on-raspberry-pi/raspberry-pi-wiring

    Right now this expects the NeoPixel DIN to be connected to GPIO pin 18.
    """

    def __init__(
        self,
        pin=None,
        num_pixels=0,
        sparking=200,
        cooling=55,
        colors=FIRE_COLORS,
        levels=LEVELS,
        color_smoothing=False,
    ):
        # The GPIO pin the pixels are attached to
        if pin is None:
            pin = board.D18
        self.pin = pin

        # The number of pixels available
        self.num_pixels = int(num_pixels)

        # Sparking: What chance (out of 255) is there that a new spark
        # will be lit?
        # Higher chance = more roaring fire.  Lower chance = more flickery fire
        # Suggested range 50-200.
        self.sparking = sparking

        # Cooling: How much does the air cool as it rises?
        # Less cooling = taller flames.  More cooling = shorter flames.
        # Suggested range 20-100
        self.cooling = cooling

        if color_smoothing:
            colors = self.rgb_color_gradient(colors)
        self.colors = [fancy.CRGB(*c) for c in colors]

        # Custom levels
        if levels is not None:
            self.levels = levels

        # Current "heat" value for each pixel
        self.heat_values = [0] * self.num_pixels

        # The pixels themselves
        self.pixels = neopixel.NeoPixel(
            self.pin,
            self.num_pixels,
            brightness=1.0,
            auto_write=False,
        )

        self.range = list(range(self.num_pixels))

    def rgb_color_gradient(self, colors):
        # Take the colors we were given and calculate a gradient between them
        color_objs = []
        for current_color, next_color in zip(colors, colors[1:] + [None]):
            if next_color is None:
                break
            color_objs += Color(rgb=current_color).range_to(
                Color(rgb=next_color),
                10,
            )

        return (c.rgb for c in color_objs)

    def cool(self):
        """ Cool down every cell a little """
        for p in range(self.num_pixels):
            self.heat_values[p] = max(
                0,
                self.heat_values[p]
                - random.uniform(
                    0,
                    ((self.cooling * 10) / self.num_pixels) + 2,
                ),
            )

    def heat(self):
        """ Heat from each pixel diffuses to its neighbors """
        for p in range(self.num_pixels):
            self.heat_values[p] = (
                self.heat_values[p - 2 if p > 0 else self.num_pixels - 2]
                + self.heat_values[p - 1 if p > 1 else self.num_pixels - 1]
                + self.heat_values[p + 1 if p < self.num_pixels - 1 else 0]
                + self.heat_values[p + 2 if p < self.num_pixels - 2 else 1]
            ) / 4

    def spark(self):
        """ Randomly ignite new 'sparks' of heat near the bottom """
        if random.randint(0, 255) < self.sparking:
            p = random.randint(0, self.num_pixels - 1)
            self.heat_values[p] = (
                self.heat_values[p] + random.uniform(160, 240)
            )

    def set_pixel_values(self):
        """ Set the pixels to the current heat values """
        random.shuffle(self.range)
        for p in self.range:
            color_index = self.heat_values[p] / 240
            color = fancy.palette_lookup(self.colors, color_index)
            color = fancy.gamma_adjust(color, brightness=self.levels)
            self.pixels[p] = color.pack()

    def __iter__(self):
        return self

    def __next__(self):
        self.cool()
        self.heat()
        self.spark()
        self.set_pixel_values()
        self.pixels.show()

    def reset(self):
        for p in range(self.num_pixels):
            self.pixels[p] = (0, 0, 0)
        self.pixels.show()


class NeoPixelFireplace(Accessory):
    category = CATEGORY_LIGHTBULB

    def __init__(self, *args, pin=18, num_pixels=120, **kwargs):

        super().__init__(*args, **kwargs)

        serv_light = self.add_preload_service(
            "Lightbulb",
            chars=[
                "On",
                # "Hue",
                # "Saturation",
                "Brightness",
            ],
        )

        # Configure our callbacks
        self.char_on = serv_light.configure_char(
            "On",
            setter_callback=self.set_state,
        )
        self.char_on = serv_light.configure_char(
            "Brightness",
            setter_callback=self.set_brightness,
        )
        # self.char_hue = serv_light.configure_char(
        #     "Hue",
        #     setter_callback=self.set_hue,
        # )
        # self.char_saturation = serv_light.configure_char(
        #     "Saturation",
        #     setter_callback=self.set_saturation,
        # )

        # Set our instance variables
        self.accessory_state = 0  # State of the neo light On/Off
        self.brightness = 40  # Brightness value 0 - 100 Homekit API
        self.hue = 0
        self.saturation = 0

        # Configure our NeoPixelFlames
        self.fire = NeoPixelFlames(num_pixels=num_pixels)

        self._stopped = False

        self.driver.loop.create_task(self.flameloop())

    def set_state(self, value):
        self.accessory_state = value

    def set_brightness(self, value):
        # "Brightness" for the fire is the sparking vs cooling. So as
        # brightness goes up, cooling goes down and sparking goes up.
        logger.info(f"Setting brightness to {value}")
        self.brightness = value
        self.fire.sparking = (self.brightness / 100) * 255
        self.fire.cooling = 100 - self.brightness
        logger.info(f"Setting brightness to {self.brightness}")
        logger.info(f"Setting sparking to {self.fire.sparking}")
        logger.info(f"Setting cooling to {self.fire.cooling}")

    def set_hue(self, hue):
        logger.info(f"Setting hue {hue}")
        self.hue = hue

    def set_saturation(self, saturation):
        logger.info(f"Setting saturation {saturation}")
        self.saturation = saturation

    async def flameloop(self):
        if self.accessory_state == 1:
            next(self.fire)
        else:
            self.fire.reset()

        if not self._stopped:
            self.driver.loop.create_task(self.flameloop())

    def stop(self):
        self._stopped = True
        self.set_state(0)
        self.fire.reset()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--state-file",
        help="path to state file",
        required=True,
    )
    parser.add_argument(
        "-a",
        "--address",
        help="local address of the accessory/bridge",
        default=get_local_address(),
    )
    parser.add_argument(
        "-n",
        "--name",
        help="the accessory name",
        default="NeoPixel Fireplace",
    )
    parser.add_argument(
        "-p",
        "--pin",
        type=int,
        help="the GPIO pin the NeoPixels are attached to",
        default=18,
    )
    parser.add_argument(
        "-x",
        "--num-pixels",
        type=int,
        help="the number of NeoPixel pixels available",
        default=120,
    )

    args = parser.parse_args()

    # Start the accessory on port 51826
    logger.info(f"Using address {args.address}")
    driver = AccessoryDriver(
        address=args.address,
        port=51826,
        persist_file=args.state_file,
    )

    # We want SIGTERM (kill) to be handled by the driver itself,
    # so that it can gracefully stop the accessory, server and
    # advertising.
    signal.signal(signal.SIGTERM, driver.signal_handler)

    driver.add_accessory(
        NeoPixelFireplace(
            driver,
            args.name,
            pin=args.pin,
            num_pixels=args.num_pixels,
        )
    )

    # Start it!
    logger.debug("Starting up")
    driver.start()


if __name__ == "__main__":
    asyncio.run(main())
