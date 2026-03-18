from gestures.base import StaticGesture


class ThumbsUp(StaticGesture):
    def detect(self, hand):
        needed = [4, 3, 8, 6, 12, 10, 16, 14, 20, 18]
        if any(hand[i] is None for i in needed):
            return False

        # thumb tip above thumb ip = thumb up
        thumb_up = hand[4][1] < hand[3][1]

        # all other fingers curled
        fingers_closed = (
            hand[8][1]  > hand[6][1]  and
            hand[12][1] > hand[10][1] and
            hand[16][1] > hand[14][1] and
            hand[20][1] > hand[18][1]
        )

        return thumb_up and fingers_closed