from gestures.base import StaticGesture
import math


def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


class Pinch(StaticGesture):
    def detect(self, hand, threshold=0.05):
        needed = [0, 4, 8, 5]
        if any(hand[i] is None for i in needed):
            return False

        # normalize by hand size so distance works at any depth
        mcp_dist = dist(hand[0], hand[5])
        pinch_dist = dist(hand[4], hand[8]) / mcp_dist

        return pinch_dist < threshold