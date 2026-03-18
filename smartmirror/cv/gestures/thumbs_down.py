from gestures.base import StaticGesture
import math


def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


class ThumbsDown(StaticGesture):
    def detect(self, hand):
        needed = [0, 4, 2, 8, 5, 12, 9, 16, 13, 20, 17]
        if any(hand[i] is None for i in needed):
            return False

        wrist    = hand[0]
        mcp_dist = dist(wrist, hand[5])

        thumb_down = (hand[4][1] - hand[2][1]) > 0.10

        index_curled  = dist(wrist, hand[8])  / mcp_dist < 1.2
        middle_curled = dist(wrist, hand[12]) / mcp_dist < 1.2
        ring_curled   = dist(wrist, hand[16]) / mcp_dist < 1.2
        pinky_curled  = dist(wrist, hand[20]) / mcp_dist < 1.2

        return thumb_down and index_curled and middle_curled and ring_curled and pinky_curled