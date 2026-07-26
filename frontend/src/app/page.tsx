"use client";

import { useEffect, FormEvent, KeyboardEvent, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type CopilotSource = {
  index: number;
  title: string;
  heading_path: string[];
  canonical_url: string;
  chunk_id: string;
  rank: number;
  content: string;
};

type CopilotResponse = {
  question: string;
  answer: string;
  grounded: boolean;
  sources: CopilotSource[];
  context_character_count: number;
  context_estimated_tokens: number;
  context_truncated: boolean;
};

type ConversationEntry = {
  id: string;
  question: string;
  response: CopilotResponse;
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://localhost:8000"
).replace(/\/$/, "");

const EXAMPLE_QUESTIONS = [
  "מה צריך לעשות כשלקוח מבקש למחוק את כרטיס הלקוח שלו?",
  "כיצד מזהים ומאמתים לקוח לפני ביצוע עסקה?",
  "מהן הפעולות הנדרשות בפתיחת סניף?",
  "מתי צריך לפנות למחלקת הציות?",
];

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getHeading(source: CopilotSource): string {
  if (source.heading_path.length === 0) {
    return "פתיח";
  }

  return source.heading_path.join(" › ");
}

type SourceInspectorEventDetail = {
  chunkId: string;
};


function dispatchSourceInspectorEvent(
  eventName: string,
  chunkId: string,
): void {
  window.dispatchEvent(
    new CustomEvent<SourceInspectorEventDetail>(
      eventName,
      {
        detail: {
          chunkId,
        },
      },
    ),
  );
}


function AnswerWithCitations({
  answer,
  sources,
}: {
  answer: string;
  sources: CopilotSource[];
}) {
  const sourceMap = useMemo(
    () => new Map(
      sources.map((source) => [
        source.index,
        source,
      ]),
    ),
    [sources],
  );

  const sourceByChunkId = useMemo(
    () => new Map(
      sources.map((source) => [
        source.chunk_id,
        source,
      ]),
    ),
    [sources],
  );

  const markdownAnswer = useMemo(
    () => answer.replace(
      /\[SOURCE\s+(\d+)\]/gi,
      (
        _match,
        rawSourceIndex: string,
      ) => {
        const sourceIndex = Number(
          rawSourceIndex,
        );
        const source = sourceMap.get(
          sourceIndex,
        );

        if (!source) {
          return `מקור ${sourceIndex}`;
        }

        return (
          `[${sourceIndex}]`
          + `(#source-${source.chunk_id})`
        );
      },
    ),
    [answer, sourceMap],
  );

  return (
    <div className="answer-content markdown-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({
            href,
            children,
            ...linkProps
          }) {
            if (
              href
              && href.startsWith("#source-")
            ) {
              const chunkId = href.slice(
                "#source-".length,
              );
              const source = (
                sourceByChunkId.get(chunkId)
              );

              if (!source) {
                return (
                  <span className="citation citation-invalid">
                    {children}
                  </span>
                );
              }

              return (
                <button
                  type="button"
                  className="citation"
                  title={
                    `${source.title} — ${
                      getHeading(source)
                    }`
                  }
                  aria-label={
                    `פתיחת מקור ${source.index}: `
                    + source.title
                  }
                  onClick={() => {
                    dispatchSourceInspectorEvent(
                      "copilot:source-open",
                      source.chunk_id,
                    );
                  }}
                  onMouseEnter={() => {
                    dispatchSourceInspectorEvent(
                      "copilot:source-highlight",
                      source.chunk_id,
                    );
                  }}
                  onMouseLeave={() => {
                    dispatchSourceInspectorEvent(
                      "copilot:source-highlight",
                      "",
                    );
                  }}
                  onFocus={() => {
                    dispatchSourceInspectorEvent(
                      "copilot:source-highlight",
                      source.chunk_id,
                    );
                  }}
                  onBlur={() => {
                    dispatchSourceInspectorEvent(
                      "copilot:source-highlight",
                      "",
                    );
                  }}
                >
                  {children}
                </button>
              );
            }

            return (
              <a
                {...linkProps}
                href={href}
                target="_blank"
                rel="noreferrer"
              >
                {children}
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="markdown-table-scroll">
                <table>{children}</table>
              </div>
            );
          },
        }}
      >
        {markdownAnswer}
      </ReactMarkdown>
    </div>
  );
}


function SourcesPanel({
  sources,
}: {
  sources: CopilotSource[];
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeChunkId, setActiveChunkId] = useState<
    string | null
  >(null);
  const [
    highlightedChunkId,
    setHighlightedChunkId,
  ] = useState<string | null>(null);

  useEffect(() => {
    function openSource(
      event: Event,
    ): void {
      const customEvent = (
        event as CustomEvent<SourceInspectorEventDetail>
      );

      const chunkId = customEvent.detail?.chunkId;

      if (!chunkId) {
        return;
      }

      const sourceExists = sources.some(
        (source) => source.chunk_id === chunkId,
      );

      if (!sourceExists) {
        return;
      }

      setIsOpen(true);
      setActiveChunkId(chunkId);
      setHighlightedChunkId(chunkId);

      window.setTimeout(() => {
        document
          .getElementById(`source-${chunkId}`)
          ?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
      }, 80);

      window.setTimeout(() => {
        setHighlightedChunkId((current) => (
          current === chunkId
            ? null
            : current
        ));
      }, 1800);
    }

    function highlightSource(
      event: Event,
    ): void {
      const customEvent = (
        event as CustomEvent<SourceInspectorEventDetail>
      );

      setHighlightedChunkId(
        customEvent.detail?.chunkId || null,
      );
    }

    window.addEventListener(
      "copilot:source-open",
      openSource,
    );

    window.addEventListener(
      "copilot:source-highlight",
      highlightSource,
    );

    return () => {
      window.removeEventListener(
        "copilot:source-open",
        openSource,
      );

      window.removeEventListener(
        "copilot:source-highlight",
        highlightSource,
      );
    };
  }, [sources]);

  if (sources.length === 0) {
    return null;
  }

  return (
    <section
      className={[
        "sources-section",
        "sources-collapsible",
        "reference-inspector",
        isOpen ? "sources-collapsible-open" : "",
      ].filter(Boolean).join(" ")}
    >
      <button
        type="button"
        className="sources-toggle"
        onClick={() => {
          setIsOpen((current) => !current);
        }}
        aria-expanded={isOpen}
      >
        <span className="sources-toggle-main">
          <span
            className="sources-toggle-icon"
            aria-hidden="true"
          >
            ◫
          </span>

          <span className="sources-toggle-text">
            <strong>מקורות</strong>
            <span>
              {sources.length}
              {" "}
              מקורות תומכים בתשובה
            </span>
          </span>
        </span>

        <span className="sources-toggle-action">
          <span className="sources-toggle-label">
            {isOpen ? "הסתרה" : "הצגה"}
          </span>

          <span
            className={[
              "sources-toggle-chevron",
              isOpen
                ? "sources-toggle-chevron-open"
                : "",
            ].filter(Boolean).join(" ")}
            aria-hidden="true"
          >
            ▾
          </span>
        </span>
      </button>

      <div
        className="sources-collapse-region"
        hidden={!isOpen}
      >
        <div className="reference-inspector-list">
          {sources.map((source) => (
            <SourceCard
              source={source}
              isExpanded={
                activeChunkId === source.chunk_id
              }
              isHighlighted={
                highlightedChunkId
                === source.chunk_id
              }
              onToggle={() => {
                setActiveChunkId((current) => (
                  current === source.chunk_id
                    ? null
                    : source.chunk_id
                ));
              }}
              key={source.chunk_id}
            />
          ))}
        </div>
      </div>
    </section>
  );
}


function getSourceKind(
  source: CopilotSource,
): {
  label: string;
  icon: string;
  tone: string;
} {
  const title = source.title.trim();

  if (title.includes("נוהל")) {
    return {
      label: "נוהל",
      icon: "▤",
      tone: "procedure",
    };
  }

  if (
    title.includes("מדריך")
    || title.includes("הדרכה")
  ) {
    return {
      label: "מדריך",
      icon: "◫",
      tone: "guide",
    };
  }

  if (
    title.includes("צ'קליסט")
    || title.includes("צ׳קליסט")
  ) {
    return {
      label: "צ׳קליסט",
      icon: "✓",
      tone: "checklist",
    };
  }

  if (
    title.includes("פורטל")
    || title === "Main Page"
  ) {
    return {
      label: "פורטל",
      icon: "◇",
      tone: "portal",
    };
  }

  return {
    label: "מסמך ידע",
    icon: "◧",
    tone: "knowledge",
  };
}


function getRelevanceLabel(
  rank: number,
): string {
  if (rank >= 4) {
    return "רלוונטי מאוד";
  }

  if (rank >= 2.5) {
    return "רלוונטי";
  }

  return "מידע משלים";
}


function SourceCard({
  source,
  isExpanded,
  isHighlighted,
  onToggle,
}: {
  source: CopilotSource;
  isExpanded: boolean;
  isHighlighted: boolean;
  onToggle: () => void;
}) {
  const [copyLabel, setCopyLabel] = useState(
    "העתקה",
  );

  const sourceContent = source.content?.trim() ?? "";
  const hasContent = sourceContent.length > 0;
  const heading = getHeading(source);
  const sourceKind = getSourceKind(source);
  const relevanceLabel = getRelevanceLabel(source.rank);

  async function copySource(): Promise<void> {
    if (!hasContent) {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        [
          source.title,
          heading,
          sourceContent,
          source.canonical_url,
        ].join("\n\n"),
      );

      setCopyLabel("הועתק ✓");

      window.setTimeout(() => {
        setCopyLabel("העתקה");
      }, 1600);
    } catch {
      setCopyLabel("העתקה נכשלה");

      window.setTimeout(() => {
        setCopyLabel("העתקה");
      }, 1600);
    }
  }

  return (
    <article
      className={[
        "source-card",
        "source-card-v2",
        "reference-inspector-card",
        `source-tone-${sourceKind.tone}`,
        isExpanded
          ? "source-card-expanded"
          : "source-card-collapsed",
        isHighlighted
          ? "source-card-highlighted"
          : "",
      ].filter(Boolean).join(" ")}
      id={`source-${source.chunk_id}`}
    >
      <div className="source-card-accent" />

      <button
        type="button"
        className="reference-source-summary"
        onClick={onToggle}
        aria-expanded={isExpanded}
      >
        <span
          className="source-document-icon"
          aria-hidden="true"
        >
          {sourceKind.icon}
        </span>

        <span className="reference-source-details">
          <span className="source-eyebrow">
            <span className="source-type-badge">
              {sourceKind.label}
            </span>

            <span className="source-number">
              מקור {source.index}
            </span>
          </span>

          <strong>{source.title}</strong>

          <span className="source-heading-path">
            {heading}
          </span>
        </span>

        <span className="reference-source-status">
          <span className="source-relevance-label">
            {relevanceLabel}
          </span>

          <span
            className={[
              "reference-source-chevron",
              isExpanded
                ? "reference-source-chevron-open"
                : "",
            ].filter(Boolean).join(" ")}
            aria-hidden="true"
          >
            ▾
          </span>
        </span>
      </button>

      {isExpanded && (
        <div className="reference-source-body">
          {hasContent ? (
            <div className="source-original-content">
              <div className="source-original-heading">
                <span aria-hidden="true">“</span>
                הקטע המקורי מתוך הוויקי
              </div>

              <div className="source-original-text">
                {sourceContent}
              </div>
            </div>
          ) : (
            <p className="reference-source-empty">
              לא קיים קטע מקורי להצגה.
            </p>
          )}

          <div className="source-actions">
            {hasContent && (
              <button
                type="button"
                className="source-icon-button"
                onClick={() => {
                  void copySource();
                }}
              >
                <span aria-hidden="true">⧉</span>
                {copyLabel}
              </button>
            )}

            <a
              className={[
                "source-icon-button",
                "source-wiki-link",
              ].join(" ")}
              href={source.canonical_url}
              target="_blank"
              rel="noreferrer"
            >
              <span aria-hidden="true">↗</span>
              פתיחה בוויקי
            </a>
          </div>
        </div>
      )}
    </article>
  );
}


export default function Home() {
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<
    ConversationEntry[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(
    null,
  );

  const canSubmit = (
    question.trim().length > 0
    && !isLoading
  );

  async function askCopilot(
    submittedQuestion?: string,
  ): Promise<void> {
    const normalizedQuestion = (
      submittedQuestion ?? question
    ).trim();

    if (!normalizedQuestion || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setQuestion("");

    try {
      const history = conversation
        .slice(-6)
        .flatMap((entry) => [
          {
            role: "user" as const,
            content: entry.question,
          },
          {
            role: "assistant" as const,
            content: entry.response.answer,
          },
        ])
        .slice(-12);

      const response = await fetch(
        `${API_BASE_URL}/api/copilot/ask/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: normalizedQuestion,
            history,
            namespace_ids: [0],
            search_limit: 30,
            max_characters: 12000,
            max_chunks: 8,
            max_chunks_per_page: 3,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          "השרת לא הצליח להתחיל את התשובה.",
        );
      }

      if (!response.body) {
        throw new Error(
          "הדפדפן לא קיבל זרם תשובה מהשרת.",
        );
      }

      const entryId = createId();

      const emptyResponse: CopilotResponse = {
        question: normalizedQuestion,
        answer: "",
        grounded: false,
        sources: [],
        context_character_count: 0,
        context_estimated_tokens: 0,
        context_truncated: false,
      };

      setConversation((current) => [
        ...current,
        {
          id: entryId,
          question: normalizedQuestion,
          response: emptyResponse,
        },
      ]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function updateEntry(
        updater: (
          responseValue: CopilotResponse,
        ) => CopilotResponse,
      ): void {
        setConversation((current) => (
          current.map((entry) => (
            entry.id === entryId
              ? {
                  ...entry,
                  response: updater(entry.response),
                }
              : entry
          ))
        ));
      }

      while (true) {
        const { value, done } = await reader.read();

        buffer += decoder.decode(
          value ?? new Uint8Array(),
          {
            stream: !done,
          },
        );

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }

          const event = JSON.parse(line) as {
            type: string;
            delta?: string;
            answer?: string;
            grounded?: boolean;
            sources?: CopilotSource[];
            question?: string;
            context_character_count?: number;
            context_estimated_tokens?: number;
            context_truncated?: boolean;
            detail?: string;
          };

          if (event.type === "metadata") {
            updateEntry((currentResponse) => ({
              ...currentResponse,
              question: (
                event.question
                ?? normalizedQuestion
              ),
              grounded: Boolean(event.grounded),
              sources: (event.sources ?? []).map(
                (source) => ({
                  ...source,
                  content: source.content ?? "",
                }),
              ),
              context_character_count: (
                event.context_character_count
                ?? 0
              ),
              context_estimated_tokens: (
                event.context_estimated_tokens
                ?? 0
              ),
              context_truncated: Boolean(
                event.context_truncated,
              ),
            }));
          }

          if (
            event.type === "delta"
            && typeof event.delta === "string"
          ) {
            updateEntry((currentResponse) => ({
              ...currentResponse,
              answer: (
                currentResponse.answer
                + event.delta
              ),
            }));

            // Give React and the browser a paint opportunity.
            // Fetch may deliver several NDJSON events in one network chunk,
            // otherwise every state update can be batched until completion.
            await new Promise<void>((resolve) => {
              window.requestAnimationFrame(() => {
                resolve();
              });
            });
          }

          if (
            event.type === "complete"
            && typeof event.answer === "string"
          ) {
            updateEntry((currentResponse) => ({
              ...currentResponse,
              answer: event.answer ?? "",
              grounded: Boolean(event.grounded),
            }));
          }

          if (event.type === "error") {
            throw new Error(
              event.detail
              ?? "יצירת התשובה נכשלה.",
            );
          }
        }

        if (done) {
          break;
        }
      }
    } catch (requestError) {
      const message = (
        requestError instanceof Error
          ? requestError.message
          : "אירעה שגיאה לא צפויה."
      );

      setError(
        `${message} ודא שה־Backend פועל ב־${API_BASE_URL}.`,
      );
      setQuestion(normalizedQuestion);
    } finally {
      setIsLoading(false);

      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    }
  }

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): void {
    event.preventDefault();
    void askCopilot();
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ): void {
    if (
      event.key === "Enter"
      && !event.shiftKey
    ) {
      event.preventDefault();

      if (canSubmit) {
        void askCopilot();
      }
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div
            className="brand-mark"
            aria-hidden="true"
          >
            ₿
          </div>

          <div>
            <strong>Bitcoin Change</strong>
            <span>Knowledge Copilot</span>
          </div>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          מחובר למאגר הידע · זיכרון שיחה פעיל
        </div>
      </header>

      <section className="workspace">
        <div className="hero">
          <div className="hero-badge">
            עוזר הידע הארגוני
          </div>

          <h1>
            איך אפשר לעזור
            <span> היום?</span>
          </h1>

          <p>
            שאלו על נהלים, הדרכות, ציות, מערכות
            ותפעול סניפים. כל תשובה מבוססת על
            מקורות מתוך הוויקי הארגוני.
          </p>
        </div>

        {conversation.length === 0 && (
          <section
            className="suggestions"
            aria-label="שאלות לדוגמה"
          >
            {EXAMPLE_QUESTIONS.map(
              (exampleQuestion) => (
                <button
                  type="button"
                  className="suggestion-card"
                  onClick={() => {
                    void askCopilot(exampleQuestion);
                  }}
                  disabled={isLoading}
                  key={exampleQuestion}
                >
                  <span className="suggestion-icon">
                    ?
                  </span>
                  <span>{exampleQuestion}</span>
                </button>
              ),
            )}
          </section>
        )}

        <section
          className="conversation"
          aria-live="polite"
        >
          {conversation.map((entry) => (
            <article
              className="conversation-entry"
              key={entry.id}
            >
              <div className="question-row">
                <div className="avatar user-avatar">
                  א
                </div>

                <div className="message user-message">
                  {entry.question}
                </div>
              </div>

              <div className="answer-row">
                <div className="avatar bot-avatar">
                  ₿
                </div>

                <div className="answer-panel">
                  <div className="answer-heading">
                    <div>
                      <span className="answer-label">
                        תשובת Copilot
                      </span>
                      <span className="grounded-label">
                        <span aria-hidden="true">✓</span>
                        מבוסס על הוויקי
                      </span>
                    </div>

                    <button
                      type="button"
                      className="copy-button"
                      onClick={() => {
                        void navigator.clipboard.writeText(
                          entry.response.answer,
                        );
                      }}
                    >
                      העתקה
                    </button>
                  </div>

                  <AnswerWithCitations
                    answer={entry.response.answer}
                    sources={entry.response.sources}
                  />

                  <SourcesPanel
                    sources={entry.response.sources}
                  />

                  <div className="answer-meta">
                    <span>
                      כ־
                      {
                        entry.response
                          .context_estimated_tokens
                      }
                      {" "}
                      טוקנים מהוויקי
                    </span>

                    {entry.response.context_truncated && (
                      <span>
                        נבחרו הקטעים הרלוונטיים ביותר
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </article>
          ))}

          {isLoading
          && (
            conversation.length === 0
            || conversation[
              conversation.length - 1
            ].response.answer.length === 0
          ) && (
            <div className="answer-row loading-row">
              <div className="avatar bot-avatar">
                ₿
              </div>

              <div className="loading-panel">
                <div className="loading-title">
                  מחפש במאגר הידע
                </div>

                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>

                <p>
                  מאתר נהלים וסעיפים רלוונטיים
                  ומנסח תשובה מבוססת.
                </p>
              </div>
            </div>
          )}
        </section>

        {error && (
          <div
            className="error-banner"
            role="alert"
          >
            <strong>לא הצלחנו לקבל תשובה</strong>
            <span>{error}</span>
          </div>
        )}

        <form
          className="composer"
          onSubmit={handleSubmit}
        >
          <label
            className="sr-only"
            htmlFor="copilot-question"
          >
            כתיבת שאלה
          </label>

          <textarea
            ref={textareaRef}
            id="copilot-question"
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
            }}
            onKeyDown={handleKeyDown}
            placeholder="שאלו שאלה על נהלי Bitcoin Change..."
            rows={1}
            maxLength={2000}
            disabled={isLoading}
          />

          <button
            type="submit"
            className="send-button"
            disabled={!canSubmit}
            aria-label="שליחת השאלה"
          >
            {isLoading ? (
              <span className="button-spinner" />
            ) : (
              <span aria-hidden="true">←</span>
            )}
          </button>

          <div className="composer-footer">
            <span>
              Enter לשליחה · Shift + Enter לשורה חדשה
            </span>
            <span>
              {question.length}/2000
            </span>
          </div>
        </form>

        <footer className="disclaimer">
          התשובות מבוססות על מאגר הידע הארגוני.
          במקרה של ספק או סתירה יש לפעול לפי הנוהל
          הרשמי ולפנות למנהל או למחלקת הציות.
        </footer>
      </section>
    </main>
  );
}
