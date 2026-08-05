from __future__ import annotations

from dataclasses import dataclass

from .detector import ActionDetector
from .models import ActionRequest


@dataclass
class CopilotActionDecision:
    is_action: bool
    action_request: ActionRequest | None = None


class CopilotActionDetector:

    def __init__(self):
        self.detector = ActionDetector()


    def detect(
        self,
        text: str,
    ) -> CopilotActionDecision:

        request = self.detector.detect(
            text
        )

        if request is None:
            return CopilotActionDecision(
                is_action=False,
                action_request=None,
            )

        return CopilotActionDecision(
            is_action=True,
            action_request=request,
        )
