"use client";

import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://localhost:8000"
).replace(/\/$/, "");

type AccountType = "branch" | "individual";

type AccountRole =
  | "branch_user"
  | "management"
  | "administrator";

type AuthAccount = {
  id: string;
  email: string;
  display_name: string;
  account_type: AccountType;
  role: AccountRole;
  branch_id: string | null;
  must_change_password: boolean;
};

type AuthSessionResponse = {
  account: AuthAccount;
  authenticated: boolean;
};

type AuthStage =
  | "loading"
  | "login"
  | "change-password"
  | "workspace";

type AuthGateProps = {
  children: ReactNode;
};

async function readErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = await response.json() as {
      detail?: string;
    };

    return payload.detail?.trim() || fallback;
  } catch {
    return fallback;
  }
}

function roleLabel(role: AccountRole): string {
  if (role === "administrator") {
    return "מנהל מערכת";
  }

  if (role === "management") {
    return "הנהלה";
  }

  return "סניף";
}

export function AuthGate({
  children,
}: AuthGateProps) {
  const [stage, setStage] = useState<AuthStage>(
    "loading",
  );
  const [account, setAccount] = useState<
    AuthAccount | null
  >(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [currentPassword, setCurrentPassword] =
    useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [error, setError] = useState<string | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const moveToLogin = useCallback(() => {
    setAccount(null);
    setStage("login");
    setPassword("");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSession(): Promise<void> {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/auth/me`,
          {
            method: "GET",
            credentials: "include",
            cache: "no-store",
          },
        );

        if (cancelled) {
          return;
        }

        if (response.status === 401) {
          moveToLogin();
          return;
        }

        if (!response.ok) {
          throw new Error(
            await readErrorMessage(
              response,
              "לא הצלחנו לבדוק את מצב ההתחברות.",
            ),
          );
        }

        const payload = (
          await response.json()
        ) as AuthSessionResponse;

        setAccount(payload.account);

        setStage(
          payload.account.must_change_password
            ? "change-password"
            : "workspace",
        );
      } catch (requestError) {
        if (cancelled) {
          return;
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : "אירעה שגיאה בבדיקת ההתחברות.",
        );

        setStage("login");
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [moveToLogin]);

  useEffect(() => {
    function requireLogin(): void {
      setError(
        "ההתחברות הסתיימה. יש להתחבר מחדש.",
      );
      moveToLogin();
    }

    function requirePasswordChange(): void {
      setError(
        "יש לבחור סיסמה חדשה לפני השימוש במערכת.",
      );
      setStage("change-password");
    }

    window.addEventListener(
      "bc-auth-required",
      requireLogin,
    );

    window.addEventListener(
      "bc-password-change-required",
      requirePasswordChange,
    );

    return () => {
      window.removeEventListener(
        "bc-auth-required",
        requireLogin,
      );

      window.removeEventListener(
        "bc-password-change-required",
        requirePasswordChange,
      );
    };
  }, [moveToLogin]);

  async function handleLogin(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/auth/login`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
            password,
          }),
        },
      );

      if (!response.ok) {
        const message = await readErrorMessage(
          response,
          "כתובת המייל או הסיסמה אינם נכונים.",
        );

        if (response.status === 423) {
          throw new Error(
            "החשבון ננעל זמנית בעקבות ניסיונות התחברות שגויים.",
          );
        }

        throw new Error(message);
      }

      const payload = (
        await response.json()
      ) as AuthSessionResponse;

      setAccount(payload.account);
      setPassword("");

      setStage(
        payload.account.must_change_password
          ? "change-password"
          : "workspace",
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "ההתחברות נכשלה.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePasswordChange(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    if (newPassword.length < 10) {
      setError(
        "הסיסמה החדשה חייבת להכיל לפחות 10 תווים.",
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setError(
        "אימות הסיסמה אינו תואם לסיסמה החדשה.",
      );
      return;
    }

    if (currentPassword === newPassword) {
      setError(
        "הסיסמה החדשה חייבת להיות שונה מהסיסמה הנוכחית.",
      );
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/auth/change-password`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
          }),
        },
      );

      if (response.status === 401) {
        moveToLogin();
        throw new Error(
          "ההתחברות הסתיימה. יש להתחבר מחדש.",
        );
      }

      if (!response.ok) {
        throw new Error(
          await readErrorMessage(
            response,
            "לא הצלחנו לשנות את הסיסמה.",
          ),
        );
      }

      const payload = (
        await response.json()
      ) as {
        account: AuthAccount;
        password_changed: boolean;
      };

      setAccount(payload.account);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setStage("workspace");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "שינוי הסיסמה נכשל.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout(): Promise<void> {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await fetch(
        `${API_BASE_URL}/api/auth/logout`,
        {
          method: "POST",
          credentials: "include",
        },
      );
    } finally {
      setIsSubmitting(false);
      moveToLogin();
    }
  }

  if (stage === "loading") {
    return (
      <main className="auth-page">
        <section
          className="auth-card auth-loading-card"
          aria-live="polite"
        >
          <div
            className="auth-brand-icon"
            aria-hidden="true"
          >
            ₿
          </div>

          <h1>BC Workspace</h1>
          <p>בודק את מצב ההתחברות...</p>

          <div
            className="auth-loading-indicator"
            aria-hidden="true"
          >
            <span />
            <span />
            <span />
          </div>
        </section>
      </main>
    );
  }

  if (stage === "login") {
    return (
      <main className="auth-page">
        <section className="auth-card">
          <div className="auth-brand">
            <div
              className="auth-brand-icon"
              aria-hidden="true"
            >
              ₿
            </div>

            <div>
              <span className="auth-eyebrow">
                Bitcoin Change
              </span>
              <h1>BC Workspace</h1>
            </div>
          </div>

          <div className="auth-heading">
            <h2>כניסה למערכת</h2>
            <p>
              יש להתחבר באמצעות כתובת המייל
              הארגונית של הסניף או ההנהלה.
            </p>
          </div>

          {error && (
            <div
              className="auth-error"
              role="alert"
            >
              {error}
            </div>
          )}

          <form
            className="auth-form"
            onSubmit={(event) => {
              void handleLogin(event);
            }}
          >
            <label htmlFor="auth-email">
              כתובת מייל
            </label>

            <input
              id="auth-email"
              type="email"
              inputMode="email"
              autoComplete="username"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
              placeholder="branch@bitcoinchange.co.il"
              required
              disabled={isSubmitting}
            />

            <label htmlFor="auth-password">
              סיסמה
            </label>

            <input
              id="auth-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
              placeholder="הקלדת סיסמה"
              required
              disabled={isSubmitting}
            />

            <button
              type="submit"
              className="auth-primary-button"
              disabled={
                isSubmitting
                || !email.trim()
                || !password
              }
            >
              {isSubmitting
                ? "מתחבר..."
                : "כניסה ל־BC Workspace"}
            </button>
          </form>

          <p className="auth-security-note">
            המערכת מיועדת לשימוש ארגוני מורשה בלבד.
          </p>
        </section>
      </main>
    );
  }

  if (
    stage === "change-password"
    && account !== null
  ) {
    return (
      <main className="auth-page">
        <section className="auth-card">
          <div className="auth-brand">
            <div
              className="auth-brand-icon"
              aria-hidden="true"
            >
              ₿
            </div>

            <div>
              <span className="auth-eyebrow">
                התחברות ראשונה
              </span>
              <h1>בחירת סיסמה חדשה</h1>
            </div>
          </div>

          <div className="auth-account-summary">
            <strong>{account.display_name}</strong>
            <span>{account.email}</span>
          </div>

          <div className="auth-heading">
            <p>
              מטעמי אבטחה יש להחליף את הסיסמה
              הראשונית לפני הכניסה למערכת.
            </p>
          </div>

          {error && (
            <div
              className="auth-error"
              role="alert"
            >
              {error}
            </div>
          )}

          <form
            className="auth-form"
            onSubmit={(event) => {
              void handlePasswordChange(event);
            }}
          >
            <label htmlFor="current-password">
              סיסמה נוכחית
            </label>

            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => {
                setCurrentPassword(
                  event.target.value,
                );
              }}
              required
              disabled={isSubmitting}
            />

            <label htmlFor="new-password">
              סיסמה חדשה
            </label>

            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => {
                setNewPassword(event.target.value);
              }}
              minLength={10}
              required
              disabled={isSubmitting}
            />

            <span className="auth-field-help">
              לפחות 10 תווים. מומלץ לשלב אותיות,
              מספרים וסימנים.
            </span>

            <label htmlFor="confirm-password">
              אימות הסיסמה החדשה
            </label>

            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => {
                setConfirmPassword(
                  event.target.value,
                );
              }}
              minLength={10}
              required
              disabled={isSubmitting}
            />

            <button
              type="submit"
              className="auth-primary-button"
              disabled={
                isSubmitting
                || !currentPassword
                || newPassword.length < 10
                || !confirmPassword
              }
            >
              {isSubmitting
                ? "שומר סיסמה..."
                : "שמירת הסיסמה וכניסה"}
            </button>

            <button
              type="button"
              className="auth-secondary-button"
              onClick={() => {
                void handleLogout();
              }}
              disabled={isSubmitting}
            >
              יציאה לחשבון אחר
            </button>
          </form>
        </section>
      </main>
    );
  }

  if (
    stage === "workspace"
    && account !== null
  ) {
    return (
      <>
        <aside className="workspace-account-bar">
          <div>
            <strong>{account.display_name}</strong>
            <span>{roleLabel(account.role)}</span>
          </div>

          <button
            type="button"
            onClick={() => {
              void handleLogout();
            }}
            disabled={isSubmitting}
          >
            יציאה
          </button>
        </aside>

        {children}
      </>
    );
  }

  return null;
}
