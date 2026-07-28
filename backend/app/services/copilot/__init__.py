from app.services.copilot.citations import (
    CitationValidationError,
    CitationValidator,
)
from app.services.copilot.models import (
    CopilotAnswer,
    CopilotConversationMessage,
    CopilotSource,
)
from app.services.copilot.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.copilot.protocol import TextGenerationClient
from app.services.copilot.providers import (
    OpenAIConfigurationError,
    OpenAIResponseError,
    OpenAITextGenerationClient,
)
from app.services.copilot.service import CopilotAnswerService

__all__ = [
    "CopilotEntity",
    "DetectedEntity",
    "EntityDetection",
    "EntityDetector",
    "MultiQueryKnowledgeContextService",
    "MultiQuerySearchReader",
    "KnowledgeQueryRetriever",
    "MultiQueryRetrievalResult",
    "MultiQueryRetrievalService",
    "QueryRewrite",
    "QueryRewriter",
    "CopilotPlanner",
    "RetrievalPlan",
    "RetrievalStrategy",
    "OpenAITextGenerationClient",
    "OpenAIResponseError",
    "OpenAIConfigurationError",
    "CitationValidationError",
    "CitationValidator",
    "CopilotAnswer",
    "CopilotAnswerService",
    "CopilotConversationMessage",
    "CopilotSource",
    "SYSTEM_PROMPT",
    "TextGenerationClient",
    "build_user_prompt",
]

from app.services.copilot.planner import (
    CopilotPlanner,
    RetrievalPlan,
    RetrievalStrategy,
)

from app.services.copilot.query_rewriter import (
    QueryRewrite,
    QueryRewriter,
)

from app.services.copilot.multi_query_retrieval import (
    KnowledgeQueryRetriever,
    MultiQueryRetrievalResult,
    MultiQueryRetrievalService,
)

from app.services.copilot.multi_query_context import (
    MultiQueryKnowledgeContextService,
    MultiQuerySearchReader,
)

from app.services.copilot.entities import (
    CopilotEntity,
    DetectedEntity,
    EntityDetection,
    EntityDetector,
)
