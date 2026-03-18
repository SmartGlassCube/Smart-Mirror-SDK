from gestures.base import StaticGesture


class OpenHand(StaticGesture):
    def detect(self, hand):
        needed = [8, 6, 12, 10, 16, 14, 20, 18]
        if any(hand[i] is None for i in needed):
            return False

        # tip.y < pip.y means finger is extended up
        return (
            hand[8][1]  < hand[6][1]  and  # index
            hand[12][1] < hand[10][1] and  # middle
            hand[16][1] < hand[14][1] and  # ring
            hand[20][1] < hand[18][1]      # pinky
        )