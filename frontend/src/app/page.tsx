"use client";

import {
  FormEvent,
  KeyboardEvent,
  useMemo,
  useRef,
  useState,
} from "react";

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

function AnswerWithCitations({
  answer,
  sources,
}: {
  answer: string;
  sources: CopilotSource[];
}) {
  const sourceMap = useMemo(
    () => new Map(
      sources.map((source) => [source.index, source]),
    ),
    [sources],
  );

  const parts = answer.split(/(\[SOURCE\s+\d+\])/gi);

  return (
    <div className="answer-content">
      {parts.map((part, index) => {
        const match = part.match(
          /^\[SOURCE\s+(\d+)\]$/i,
        );

        if (!match) {
          return (
            <span key={`${index}-${part.slice(0, 10)}`}>
              {part}
            </span>
          );
        }

        const sourceIndex = Number(match[1]);
        const source = sourceMap.get(sourceIndex);

        if (!source) {
          return (
            <span
              className="citation citation-invalid"
              key={`${index}-${sourceIndex}`}
            >
              מקור {sourceIndex}
            </span>
          );
        }

        return (
          <a
            className="citation"
            href={`#source-${source.chunk_id}`}
            title={`${source.title} — ${getHeading(source)}`}
            key={`${index}-${sourceIndex}`}
          >
            {sourceIndex}
          </a>
        );
      })}
    </div>
  );
}

function SourceCard({
  source,
}: {
  source: CopilotSource;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copyLabel, setCopyLabel] = useState(
    "העתקת הקטע",
  );

  const sourceContent = source.content?.trim() ?? "";
  const hasContent = sourceContent.length > 0;

  async function copySource(): Promise<void> {
    if (!hasContent) {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        [
          source.title,
          getHeading(source),
          sourceContent,
          source.canonical_url,
        ].join("\n\n"),
      );

      setCopyLabel("הועתק ✓");

      window.setTimeout(() => {
        setCopyLabel("העתקת הקטע");
      }, 1600);
    } catch {
      setCopyLabel("ההעתקה נכשלה");

      window.setTimeout(() => {
        setCopyLabel("העתקת הקטע");
      }, 1600);
    }
  }

  return (
    <article
      className={[
        "source-card",
        isExpanded ? "source-card-expanded" : "",
      ].filter(Boolean).join(" ")}
      id={`source-${source.chunk_id}`}
    >
      <div className="source-card-header">
        <div className="source-index">
          {source.index}
        </div>

        <div className="source-details">
          <h4>{source.title}</h4>
          <p>{getHeading(source)}</p>
        </div>
      </div>

      <div className="source-actions">
        {hasContent && (
          <button
            type="button"
            className="source-action-button"
            onClick={() => {
              setIsExpanded((current) => !current);
            }}
            aria-expanded={isExpanded}
          >
            <span aria-hidden="true">
              {isExpanded ? "▴" : "▾"}
            </span>
            {isExpanded
              ? "הסתרת הקטע המקורי"
              : "הצגת הקטע המקורי"}
          </button>
        )}

        {hasContent && (
          <button
            type="button"
            className="source-action-button"
            onClick={() => {
              void copySource();
            }}
          >
            <span aria-hidden="true">⧉</span>
            {copyLabel}
          </button>
        )}

        <a
          className="source-wiki-link"
          href={source.canonical_url}
          target="_blank"
          rel="noreferrer"
        >
          <span aria-hidden="true">↗</span>
          פתיחת המסמך בוויקי
        </a>
      </div>

      {isExpanded && hasContent && (
        <div className="source-original-content">
          <div className="source-original-heading">
            הקטע המקורי מתוך הוויקי
          </div>

          <div className="source-original-text">
            {sourceContent}
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

                  <div className="sources-section">
                    <div className="sources-heading">
                      <h3>מקורות</h3>
                      <span>
                        {entry.response.sources.length}
                        {" "}
                        מקורות נמצאו
                      </span>
                    </div>

                    <div className="sources-grid">
                      {entry.response.sources.map(
                        (source) => (
                          <SourceCard
                            source={source}
                            key={source.chunk_id}
                          />
                        ),
                      )}
                    </div>
                  </div>

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
