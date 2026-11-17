# Extending the Smart Mirror SDK

Everything below plugs in from your own app code. None of it requires editing the SDK packages in `backend/glasscube/`. The mirror app's own pages are in `backend/glasscube/app/pages.py`: a good place to start.

| You want to add… | Python | Frontend |
|---|---|---|
| A gesture | Subclass `Gesture`; add it to the `GestureDetector` | — |
| A widget | Subclass `BaseWidget` and set `type` | Add a `frontend/src/widgets/<type>/` folder |
| A page | Add a node (and edges) to the graph | — |
| A reaction to a gesture | Use a graph edge, `event_bindings`, or `widget.handle_gesture` | — |

---

## 1. Add a gesture

A gesture is a class whose `detect(context)` runs once per camera frame and returns the events it fired. Event names are plain strings, so a custom gesture doesn't need to edit `GestureType`.

```python
from glasscube.vision import Gesture, GestureEvent, SIDES

class FistGesture(Gesture):
    name = "fist"

    def __init__(self):
        self._was_fist = {side: False for side in SIDES}

    def detect(self, context):
        events = []
        for side in SIDES:
            hand = context.hands[side]
            is_fist = hand.detected and not any(
                context.signals[finger][side] for finger in ("index_up", "middle_up", "ring_up", "pinky_up")
            )
            if is_fist and not self._was_fist[side]:
                events.append(GestureEvent(type="fist", hand=side, location=hand.palm_center))
            self._was_fist[side] = is_fist
        return events
```

Register it alongside the built-ins:

```python
from glasscube.vision import GestureDetector, default_gesture_set

detector = GestureDetector(gestures=default_gesture_set() + [FistGesture()])
server = SmartMirrorServer(state_manager=state_manager, gesture_detector=detector)
```

**Inputs available in `context`:**
- `context.hands["left" | "right"]`: `HandData`, which has `landmarks` (21 × `(x, y, z)`), `palm_center`, `bbox`, `is_raised` and `detected`.
- `context.signals`: shared per-frame features, computed once. The full table is in [vision.md](vision.md#signals).
- `context.timestamp`: the frame time in seconds.

**Base classes for common gesture shapes** (in `glasscube.vision`):
- `ContinuousGesture`: for start → update → end gestures. Call `self._phase(side, triggered, ended, (start, update, end), location, data)` once per hand per frame. `ScrollGesture` and `ZoomGesture` use it.
- `PostureSwipeGesture`: a one-hand swipe while holding a posture. Implement `is_ready(context, side)` and `tracked_point(context, side)`, and set `directions = {"left": ..., "right": ..., "up": ..., "down": ...}`. `SwipeGesture` and `TwoFingersSwipeGesture` are about 20 lines each on top of it.

Try a new gesture with `backend/examples/gesture_detector_debug.py`: add it to the list and watch the event feed.

---

## 2. Add a widget (component)

A widget has two halves that share one `type` string: a Python model (state + data) and a React component (rendering).

### Python model

```python
from glasscube.widgets import BaseWidget

class ClockWidget(BaseWidget):
    type = "clock"          # must match the frontend folder's defineWidget('clock', ...)
    refresh_interval = 1    # seconds between data_provider calls

clock = ClockWidget(
    position={"x": 0.9, "y": 0.1},            # 0..1 fractions of the screen
    data_provider=lambda: {"now": time.strftime("%H:%M:%S")},
)
```

`BaseWidget(...)` accepts `position`, `content`, `data`, `data_provider`, `refresh_interval`, `metadata`, `gestures`, `draggable` (default `True`) and `widget_id`. For a one-off widget you can skip the subclass: `BaseWidget(widget_type="clock", ...)`.

Optional hooks:

| Hook | When it's used |
|---|---|
| `data_provider` | Any callable, sync or async, taking `(widget)` or `()`. Its return value becomes `widget.data`, and the frontend is updated when it changes. |
| `gestures = ("fist", ...)` + `handle_gesture(event) -> bool` | The widget receives these events when it is the one targeted (nearest to the hand). Return `True` if its state changed. Return `False` to fall through to the default bindings. |
| `apply_navigation(horizontal_steps, vertical_steps) -> bool` | Opts into the default swipe/scroll bindings. `TextWidget` is the reference implementation. |
| `serialize()` | Adds fields for the frontend. Call `super().serialize()` and extend its result. |

### React component

Create a folder `frontend/src/widgets/clock/` containing two files:

```tsx
// ClockWidget.tsx
import type { WidgetProps } from '../defineWidget'

type ClockData = { now?: string }

const ClockWidget = ({ widget }: WidgetProps<ClockData>) => (
  <div className="widget clock-widget">
    <h2>{widget.data?.now ?? '--:--'}</h2>
  </div>
)

export default ClockWidget
```

```ts
// index.ts
import { defineWidget } from '../defineWidget'
import ClockWidget from './ClockWidget'

export default defineWidget('clock', ClockWidget)
```

That's all. `widgets/registry.ts` discovers every `widgets/*/index.ts` automatically. The component receives the serialized widget (`id`, `type`, `position`, `content`, `data`, `metadata`, `dragging`). Positioning and drag highlighting are handled by `WidgetSlot`. The shared `.widget` class gives the standard card look.

---

## 3. Add a page

Pages are the nodes of a graph. Edges switch pages when their gesture fires on the current page.

```python
graph = {
    "nodes": [
        {"id": "home", "widgets": [clock, weather]},
        {"id": "agenda", "widgets": [calendar]},
    ],
    "edges": [
        {"from": "home", "to": "agenda", "gesture": "two_fingers_swipe_left"},
        {"from": "agenda", "to": "home", "gesture": "two_fingers_swipe_right"},
        {"from": "agenda", "to": "home", "gesture": "fist"},   # custom gestures work too
    ],
}
state_manager = StateManager(graph=graph, initial_node_id="home")
```

Edges also accept `source`/`target` instead of `from`/`to`, and `trigger`/`event` instead of `gesture`. To jump to a page from any page, use an event binding (next section).

---

## 4. React to gestures at the app level

`StateManager` handles each event in three stages and stops at the first one that changes state:

1. **`event_bindings`**: app-wide actions.
   ```python
   StateManager(graph=graph, event_bindings={
       "right_click": {"method": "set_current_node", "kwargs": {"node_id": "home"}},
       "fist": lambda state_manager, event: print("fist!") or False,
       "zoom_update_pinky_up": {"target": "current_widget", "method": "zoom"},  # calls widget.zoom(event=...)
   })
   ```
   An action is a callable `(state_manager, event)`, a `StateManager` method name, or `{"target", "method", "kwargs"}`. Return `True` from it to broadcast the new state.
2. **Graph edges** from the current page (section 3).
3. **Widget events**: first `handle_gesture` on widgets that list the event in `gestures`, then the default bindings in `glasscube/config/json_config/default_widget_event_bindings.json`:

   | Event | Handler | `target` |
   |---|---|---|
   | `swipe_left/right/up/down` | `_handle_widget_navigation` | `navigable` (has `apply_navigation`) |
   | `scroll_start/update` | `_handle_widget_scroll` | `navigable` |
   | `pinch_start` | `_handle_widget_drag_start` | `draggable` |
   | `pinch_move`, `pinch_end` | `_handle_widget_drag_move/_end` | `none` (uses the grabbed widget) |

   Override or add bindings with `StateManager(widget_event_bindings={...})`, and tune thresholds with `gesture_config={...}` (see `default_gesture_config.json`). The target widget is the matching widget nearest to the hand within `target_radius`. If none is that close, the page's first matching widget is used.
