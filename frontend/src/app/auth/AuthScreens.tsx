import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError } from "../../api/client";
import {
  findIdRequestCode,
  findIdVerify,
  login,
  passwordResetConfirm,
  passwordResetRequestCode,
  signupComplete,
  signupRequestCode,
} from "../../api/auth";
import type { AuthUser } from "../../types/auth";

export type AuthView = "login" | "signup" | "find-id" | "password-reset";

const LOGIN_ID_RE = /^[a-z0-9][a-z0-9._-]{3,29}$/;

function fieldClassName(invalid?: boolean): string {
  return [
    "w-full rounded-xl border bg-background px-3 py-2.5 text-sm outline-none",
    "focus:border-primary focus:ring-2 focus:ring-primary/20",
    invalid ? "border-destructive" : "border-border",
  ].join(" ");
}

function AuthShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary text-white font-bold mb-3">
            P
          </div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">PickNext</h1>
          <p className="text-sm text-muted-foreground mt-1">{title}</p>
        </div>
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}

function ErrorText({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="text-sm text-destructive" role="alert">
      {message}
    </p>
  );
}

function LinkButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm text-primary hover:underline"
    >
      {children}
    </button>
  );
}

export function LoginView({
  onLoggedIn,
  onNavigate,
}: {
  onLoggedIn: (user: AuthUser) => void;
  onNavigate: (view: AuthView) => void;
}) {
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const user = await login({
        login_id: loginId.trim().toLowerCase(),
        password,
        remember_me: rememberMe,
      });
      onLoggedIn(user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "로그인에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell title="로그인">
      <form className="space-y-4" onSubmit={(e) => void submit(e)}>
        <div className="space-y-1.5">
          <label htmlFor="login-id" className="text-sm font-medium text-foreground">
            아이디
          </label>
          <input
            id="login-id"
            name="username"
            autoComplete="username"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="login-password" className="text-sm font-medium text-foreground">
            비밀번호
          </label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="rounded border-border"
          />
          자동 로그인
        </label>
        <ErrorText message={error} />
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {pending ? "로그인 중…" : "로그인"}
        </button>
      </form>
      <div className="mt-5 flex flex-wrap gap-3 justify-center">
        <LinkButton onClick={() => onNavigate("signup")}>회원가입</LinkButton>
        <LinkButton onClick={() => onNavigate("find-id")}>아이디 찾기</LinkButton>
        <LinkButton onClick={() => onNavigate("password-reset")}>비밀번호 찾기</LinkButton>
      </div>
    </AuthShell>
  );
}

export function SignupView({
  onNavigate,
}: {
  onNavigate: (view: AuthView) => void;
}) {
  const [loginId, setLoginId] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [lockedLoginId, setLockedLoginId] = useState<string | null>(null);
  const [lockedEmail, setLockedEmail] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  const contextStale =
    lockedLoginId != null &&
    lockedEmail != null &&
    (loginId.trim().toLowerCase() !== lockedLoginId ||
      email.trim().toLowerCase() !== lockedEmail);

  const requestCode = async () => {
    setError(null);
    setInfo(null);
    const normalizedId = loginId.trim().toLowerCase();
    const normalizedEmail = email.trim().toLowerCase();
    if (!LOGIN_ID_RE.test(normalizedId)) {
      setError("아이디 형식이 올바르지 않습니다.");
      return;
    }
    setPending(true);
    try {
      const res = await signupRequestCode({
        login_id: normalizedId,
        email: normalizedEmail,
      });
      setLockedLoginId(normalizedId);
      setLockedEmail(normalizedEmail);
      setCooldown(60);
      setInfo(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "인증번호 요청에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (contextStale || lockedLoginId == null || lockedEmail == null) {
      setError("아이디 또는 이메일이 변경되었습니다. 인증번호를 다시 요청하세요.");
      return;
    }
    if (password !== passwordConfirm) {
      setError("비밀번호 확인이 일치하지 않습니다.");
      return;
    }
    if (password.length < 10) {
      setError("비밀번호는 10자 이상이어야 합니다.");
      return;
    }
    setPending(true);
    try {
      await signupComplete({
        login_id: lockedLoginId,
        email: lockedEmail,
        verification_code: code.trim(),
        password,
        password_confirm: passwordConfirm,
      });
      onNavigate("login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell title="회원가입">
      <form className="space-y-4" onSubmit={(e) => void submit(e)}>
        <div className="space-y-1.5">
          <label htmlFor="signup-id" className="text-sm font-medium">아이디</label>
          <input
            id="signup-id"
            autoComplete="username"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="signup-email" className="text-sm font-medium">이메일</label>
          <input
            id="signup-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={pending || cooldown > 0}
            onClick={() => void requestCode()}
            className="rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            {cooldown > 0 ? `재전송 ${cooldown}s` : "인증번호 요청"}
          </button>
        </div>
        {contextStale && (
          <p className="text-xs text-amber-700">
            아이디/이메일이 변경되어 기존 인증번호는 사용할 수 없습니다.
          </p>
        )}
        <div className="space-y-1.5">
          <label htmlFor="signup-code" className="text-sm font-medium">인증번호</label>
          <input
            id="signup-code"
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className={fieldClassName()}
            required
            maxLength={6}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="signup-password" className="text-sm font-medium">비밀번호</label>
          <input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="signup-password2" className="text-sm font-medium">비밀번호 확인</label>
          <input
            id="signup-password2"
            type="password"
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            className={fieldClassName()}
            required
          />
        </div>
        {info && <p className="text-sm text-muted-foreground">{info}</p>}
        <ErrorText message={error} />
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium disabled:opacity-50"
        >
          회원가입 완료
        </button>
      </form>
      <div className="mt-5 text-center">
        <LinkButton onClick={() => onNavigate("login")}>로그인으로</LinkButton>
      </div>
    </AuthShell>
  );
}

export function FindIdView({
  onNavigate,
}: {
  onNavigate: (view: AuthView) => void;
}) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [foundId, setFoundId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  const requestCode = async () => {
    setError(null);
    setFoundId(null);
    setPending(true);
    try {
      const res = await findIdRequestCode({ email: email.trim().toLowerCase() });
      setInfo(res.message);
      setCooldown(60);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "요청에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  const verify = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await findIdVerify({
        email: email.trim().toLowerCase(),
        verification_code: code.trim(),
      });
      setFoundId(res.login_id);
      setInfo(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "확인에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell title="아이디 찾기">
      {foundId ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-muted-foreground">가입 아이디</p>
          <p className="text-lg font-semibold text-foreground">{foundId}</p>
          <button
            type="button"
            onClick={() => onNavigate("login")}
            className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium"
          >
            로그인으로
          </button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={(e) => void verify(e)}>
          <div className="space-y-1.5">
            <label htmlFor="find-email" className="text-sm font-medium">이메일</label>
            <input
              id="find-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={fieldClassName()}
              required
            />
          </div>
          <button
            type="button"
            disabled={pending || cooldown > 0}
            onClick={() => void requestCode()}
            className="rounded-xl border border-border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {cooldown > 0 ? `재전송 ${cooldown}s` : "인증번호 요청"}
          </button>
          <div className="space-y-1.5">
            <label htmlFor="find-code" className="text-sm font-medium">인증번호</label>
            <input
              id="find-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={fieldClassName()}
              required
              maxLength={6}
            />
          </div>
          {info && <p className="text-sm text-muted-foreground">{info}</p>}
          <ErrorText message={error} />
          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium disabled:opacity-50"
          >
            아이디 확인
          </button>
        </form>
      )}
      {!foundId && (
        <div className="mt-5 text-center">
          <LinkButton onClick={() => onNavigate("login")}>로그인으로</LinkButton>
        </div>
      )}
    </AuthShell>
  );
}

export function PasswordResetView({
  onNavigate,
}: {
  onNavigate: (view: AuthView) => void;
}) {
  const [loginId, setLoginId] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  const requestCode = async () => {
    setError(null);
    setPending(true);
    try {
      const res = await passwordResetRequestCode({
        login_id: loginId.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
      });
      setInfo(res.message);
      setCooldown(60);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "요청에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password !== passwordConfirm) {
      setError("비밀번호 확인이 일치하지 않습니다.");
      return;
    }
    setPending(true);
    try {
      await passwordResetConfirm({
        login_id: loginId.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
        verification_code: code.trim(),
        new_password: password,
        new_password_confirm: passwordConfirm,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "재설정에 실패했습니다.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell title="비밀번호 찾기">
      {done ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-foreground">비밀번호가 재설정되었습니다.</p>
          <button
            type="button"
            onClick={() => onNavigate("login")}
            className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium"
          >
            로그인으로
          </button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={(e) => void submit(e)}>
          <div className="space-y-1.5">
            <label htmlFor="reset-id" className="text-sm font-medium">아이디</label>
            <input
              id="reset-id"
              autoComplete="username"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              className={fieldClassName()}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="reset-email" className="text-sm font-medium">이메일</label>
            <input
              id="reset-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={fieldClassName()}
              required
            />
          </div>
          <button
            type="button"
            disabled={pending || cooldown > 0}
            onClick={() => void requestCode()}
            className="rounded-xl border border-border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {cooldown > 0 ? `재전송 ${cooldown}s` : "인증번호 요청"}
          </button>
          <div className="space-y-1.5">
            <label htmlFor="reset-code" className="text-sm font-medium">인증번호</label>
            <input
              id="reset-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={fieldClassName()}
              required
              maxLength={6}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="reset-password" className="text-sm font-medium">새 비밀번호</label>
            <input
              id="reset-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={fieldClassName()}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="reset-password2" className="text-sm font-medium">새 비밀번호 확인</label>
            <input
              id="reset-password2"
              type="password"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className={fieldClassName()}
              required
            />
          </div>
          {info && <p className="text-sm text-muted-foreground">{info}</p>}
          <ErrorText message={error} />
          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-xl bg-primary text-white py-2.5 text-sm font-medium disabled:opacity-50"
          >
            비밀번호 재설정
          </button>
        </form>
      )}
      {!done && (
        <div className="mt-5 text-center">
          <LinkButton onClick={() => onNavigate("login")}>로그인으로</LinkButton>
        </div>
      )}
    </AuthShell>
  );
}

export function AuthLoadingSplash() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary text-white text-xl font-bold animate-pulse">
          P
        </div>
        <p className="text-sm text-muted-foreground">PickNext 불러오는 중…</p>
      </div>
    </div>
  );
}
