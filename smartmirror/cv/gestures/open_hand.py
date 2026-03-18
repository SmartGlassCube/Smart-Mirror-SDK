from gestures.base import StaticGesture
import math


def distance(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


class OpenHand(StaticGesture):
    def detect(self, hand):
        needed = [0, 4, 8, 12, 16, 20, 5]
        if any(hand[i] is None for i in needed):
            return False

        wrist          = hand[0]
        index_mcp_dist = distance(wrist, hand[5])

        index_extended  = distance(wrist, hand[8])  / index_mcp_dist > 1.5
        middle_extended = distance(wrist, hand[12]) / index_mcp_dist > 1.5
        ring_extended   = distance(wrist, hand[16]) / index_mcp_dist > 1.5
        pinky_extended  = distance(wrist, hand[20]) / index_mcp_dist > 1.3
        thumb_extended  = distance(wrist, hand[4])  / index_mcp_dist > 0.9

        return index_extended and middle_extended and ring_extended and pinky_extended and thumb_extended