"""Keep downlink Opus ahead of the speaker without overflowing it.

xiaozhi-esp32 v2.5.2 queues at most 20 decode packets
(MAX_DECODE_PACKETS_IN_QUEUE = 1200 / 60). PushPacketToDecodeQueue drops a
packet when that queue is full. Sleeping a full frame after every send falls
behind playback, and the voice breaks up. The first `lead` frames go out
together. Later frames wait only while that many are still ahead of the speaker.
If synthesis stalls and the cushion is already gone, the next frames start a
new cushion instead of being dumped in one burst.
"""

from __future__ import annotations

DEVICE_DECODE_QUEUE = 20
LEAD_MARGIN = 4


class PlaybackClock:
    def __init__(self, frame_s: float, lead_frames: int) -> None:
        self.frame_s = frame_s
        self.lead = max(1, min(int(lead_frames), DEVICE_DECODE_QUEUE - LEAD_MARGIN))
        self.mark: int | None = None
        self.sent_in_mark = 0
        self.total = 0

    def wait_before(self, now: float) -> float:
        if self.frame_s <= 0 or self.mark is None:
            return 0.0
        queued = self._queued(now)
        if queued < -1:
            self.mark = None
            self.sent_in_mark = 0
            return 0.0
        if queued <= self.lead - 1:
            return 0.0
        frame_ms = self._frame_ms()
        return (queued - (self.lead - 1)) * frame_ms / 1000

    def note_sent(self, now: float) -> None:
        if self.mark is None:
            self.mark = self._ms(now)
            self.sent_in_mark = 0
        self.sent_in_mark += 1
        self.total += 1

    def queued(self, now: float) -> float:
        if self.mark is None or self.frame_s <= 0:
            return float(self.sent_in_mark)
        return float(self._queued(now))

    def _frame_ms(self) -> int:
        return max(1, int(round(self.frame_s * 1000)))

    def _ms(self, seconds: float) -> int:
        return int(round(seconds * 1000))

    def _queued(self, now: float) -> int:
        consumed = max(0, self._ms(now) - int(self.mark or 0)) // self._frame_ms()
        return self.sent_in_mark - consumed
