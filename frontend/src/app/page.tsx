"use client";

import { FormEvent, useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  version: string;
};

const portals = [
  {
    icon: "👤",
    title: "נציגים",
    description: "שירות לקוחות, עסקאות ותפעול סניף",
  },
  {
    icon: "🏢",
    title: "מנהלי סניפים",
    description: "ניהול צוות, בקרה ושגרות עבודה",
  },
  {
    icon: "⚖️",
    title: "ציות ורגולציה",
    description: "KYC, AML, חריגים והנחיות ציות",
  },
  {
    icon: "🎓",
    title: "הדרכות",
    description: "קליטת עובדים, חומרי לימוד ומבחנים",
  },
  {
    icon: "⚙️",
    title: "מערכות",
    description: "Salesforce, Lamassu וכלי עבודה",
  },
  {
    icon: "📋",
    title: "צ׳קליסטים",
    description: "הנחיות קצרות לביצוע בזמן אמת",
  },
];

export default function Home() {
  const [question, setQuestion] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [submittedQuestion, setSubmittedQuestion] = useState("");

  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    const controller = new AbortController();

    async function checkBackend() {
      try {
        const response = await fetch(`${apiUrl}/api/health`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const data = (await response.json()) as HealthResponse;
        setHealth(data);
        setConnectionError(false);
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setConnectionError(true);
        }
      }
    }

    void checkBackend();

    return () => controller.abort();
  }, [apiUrl]);

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedQuestion = question.trim();

    if (!normalizedQuestion) {
      return;
    }

    setSubmittedQuestion(normalizedQuestion);
  }

  return (
    <main>
      <header className="topbar">
        <div className="brand">
          <div className="brandMark">₿</div>

          <div>
            <strong>Bitcoin Change</strong>
            <span>Knowledge Copilot</span>
          </div>
        </div>

        <div
          className={`systemStatus ${
            health?.status === "ok" ? "online" : "offline"
          }`}
        >
          <span className="statusDot" />

          {health?.status === "ok"
            ? `המערכת מחוברת · API ${health.version}`
            : connectionError
              ? "ה־Backend אינו מחובר"
              : "בודק חיבור..."}
        </div>
      </header>

      <section className="hero">
        <div className="heroContent">
          <div className="eyebrow">סביבת הידע הארגונית</div>

          <h1>
            כל הידע של
            <br />
            <span>Bitcoin Change.</span>
          </h1>

          <p>
            חיפוש נהלים, תהליכים, מערכות והדרכות מתוך מקור ידע ארגוני
            מאושר.
          </p>

          <form className="searchBox" onSubmit={submitQuestion}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="לדוגמה: איך סוגרים יום בסניף?"
              aria-label="שאלה ל־Bitcoin Change Copilot"
            />

            <button type="submit">חפש</button>
          </form>

          <div className="suggestions">
            {[
              "איך סוגרים יום?",
              "אילו מסמכים צריך מלקוח זר?",
              "מה עושים אם יש פער בקופה?",
            ].map((suggestion) => (
              <button
                type="button"
                key={suggestion}
                onClick={() => setQuestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className="heroCard">
          <div className="assistantLogo">BC</div>
          <span>Bitcoin Change Copilot</span>
          <strong>מקור ידע אחד. תשובות מדויקות.</strong>

          <ul>
            <li>תשובות מתוך מסמכים מאושרים</li>
            <li>הצגת מקור וגרסה</li>
            <li>חיפוש לפי הקשר ותפקיד</li>
          </ul>
        </div>
      </section>

      {submittedQuestion && (
        <section className="resultPanel">
          <div>
            <span>השאלה שנשלחה</span>
            <h2>{submittedQuestion}</h2>
          </div>

          <div className="resultMessage">
            <strong>שלד המוצר פועל בהצלחה.</strong>

            <p>
              החיפוש התקבל בממשק האמיתי. בשלב הבא נחבר את הפעולה הזאת
              ל־MediaWiki API, כך שהתוצאה תגיע מתוך דפי הוויקי ולא מתוכן
              הדגמה.
            </p>
          </div>
        </section>
      )}

      <section className="portalSection">
        <div className="sectionTitle">
          <span>ניווט ארגוני</span>
          <h2>הפורטלים המרכזיים</h2>
        </div>

        <div className="portalGrid">
          {portals.map((portal) => (
            <button className="portalCard" key={portal.title}>
              <span className="portalIcon">{portal.icon}</span>
              <strong>{portal.title}</strong>
              <p>{portal.description}</p>
              <span className="portalLink">כניסה לפורטל ←</span>
            </button>
          ))}
        </div>
      </section>

      <footer>
        <strong>Bitcoin Change Enterprise Knowledge Platform</strong>
        <span>MVP Foundation · Release 0.1.0</span>
      </footer>
    </main>
  );
}
