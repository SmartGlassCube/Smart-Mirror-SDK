class GestureDetector:
    def __init__(self):
        pass

# Expected output of GestureDetector.process_frame(frame):
#
# {
#     "hands": {
#         "left": HandData(...),
#         "right": HandData(...),
#     },
#     "signals": {
#         "hand_count": int,
#         "pinching": {
#             "left": bool,
#             "right": bool,
#         },
#         "both_hands_raised": bool,
#     },
#     "events": [
#         GestureEvent(type=GestureType.PINCH_START, hand="right"),
#         GestureEvent(type=GestureType.SWIPE_LEFT, hand="left"),
#     ]
# }
#
# Meaning:
# - "hands"   : structured per-hand frame data coming from LandmarkDetector
# - "signals" : continuous states that are true right now
# - "events"  : transition-like gestures detected on this frame only