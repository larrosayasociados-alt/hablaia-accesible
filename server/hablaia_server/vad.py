"""Energy gate for listen mode "auto".

v2.5.2 starts in kListeningModeAutoStop when server AEC is off
(Application::GetDefaultListeningMode). In that mode the device streams Opus
until the server sends tts start. It does not send listen stop at the end of
a sentence. This gate is a preview, not a speech recogniser.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnergyGate:
    speech_frames: int = 0
    silence_frames: int = 0
    threshold: float = 450.0
    min_speech_frames: int = 4
    # 18 frames at 60 ms is a little over a second. A shorter pause cuts a
    # person who stops to think in the middle of a sentence.
    silence_needed: int = 18

    def feed(self, rms: float) -> bool:
        if rms >= self.threshold:
            self.speech_frames += 1
            self.silence_frames = 0
            return False
        if self.speech_frames >= self.min_speech_frames:
            self.silence_frames += 1
            return self.silence_frames >= self.silence_needed
        return False

    def reset(self) -> None:
        self.speech_frames = 0
        self.silence_frames = 0
