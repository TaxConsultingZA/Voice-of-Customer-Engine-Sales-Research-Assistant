"""
Rule-based taxonomy classifier mapping complaint text to UEC taxonomy paths.
Format: Domain.Capability.Theme  (e.g. Authentication.Login.PasswordReset)
Signal Alpha: Authentication.* and Onboarding.* — highest priority domains.
"""

# Order matters: more specific rules before generic ones within each domain.
_RULES: list[tuple[list[str], str]] = [
    # ── Authentication (Signal Alpha) ────────────────────────────────────────
    (
        ["password reset", "forgot password", "reset link", "reset email", "reset password"],
        "Authentication.Login.PasswordReset",
    ),
    (
        ["mfa", "2fa", "two-factor", "two factor", "verification code", "authenticator app", "otp"],
        "Authentication.Login.MultiFactorAuth",
    ),
    (
        ["locked out", "account locked", "account suspended", "too many attempts"],
        "Authentication.Login.AccountLocked",
    ),
    (["sso", "single sign-on", "saml", "oauth"], "Authentication.SSO.Failure"),
    (
        ["invalid credentials", "wrong password", "incorrect password"],
        "Authentication.Login.InvalidCredentials",
    ),
    (
        ["session expired", "logged out", "session timeout", "kicked out"],
        "Authentication.Login.SessionExpired",
    ),
    (
        [
            "log in",
            "login",
            "sign in",
            "cannot access",
            "can't log",
            "access my account",
            "kan nie inlog",
            "akusebenzi ukungena",
        ],
        "Authentication.Login.Failure",
    ),
    # ── Onboarding (Signal Alpha) ────────────────────────────────────────────
    (
        ["verification email", "verify email", "confirmation email", "activate account"],
        "Onboarding.Registration.EmailVerification",
    ),
    (
        ["sign up", "signup", "create account", "register", "registration"],
        "Onboarding.Registration.Failure",
    ),
    (
        ["setup wizard", "onboarding", "getting started", "initial setup", "welcome email"],
        "Onboarding.Setup.Failure",
    ),
    # ── Compliance ───────────────────────────────────────────────────────────
    (
        [
            "personal data",
            "my data",
            "data copy",
            "right of access",
            "section 23",
            "popia",
            "gdpr",
            "delete my data",
        ],
        "Compliance.Popia.DataAccessRequest",
    ),
    # ── Billing ──────────────────────────────────────────────────────────────
    (
        [
            "cancel my subscription",
            "cancel subscription",
            "cancellation",
            "terminate",
            "kanselleer my intekening",
        ],
        "Billing.Subscription.Cancellation",
    ),
    (["refund", "money back", "reimburs"], "Billing.Payment.Refund"),
    (
        ["charged twice", "duplicate charge", "double charge", "overcharged"],
        "Billing.Payment.DuplicateCharge",
    ),
    (
        [
            "payment fail",
            "payment declin",
            "card declin",
            "card fail",
            "payment not going through",
            "failing at checkout",
            "payment keeps",
            "betaling misluk",
            "inkokhelo yehluleka",
        ],
        "Billing.Payment.Failure",
    ),
    (["invoice", "billing", "subscription cost", "pricing"], "Billing.Invoice.Query"),
    # ── Performance ──────────────────────────────────────────────────────────
    (
        ["down", "outage", "unavailable", "503", "500 error", "service unavailable"],
        "Performance.Availability.Outage",
    ),
    (
        ["slow", "timeout", "loading forever", "takes forever", "hangs", "freezing"],
        "Performance.Latency.Degradation",
    ),
    # ── Reporting ────────────────────────────────────────────────────────────
    (
        ["dashboard", "export", "report", "analytics", "graph", "chart"],
        "Reporting.Dashboard.Failure",
    ),
    # ── Integration ──────────────────────────────────────────────────────────
    (["api", "webhook", "integration", "sync", "connector", "zapier"], "Integration.API.Failure"),
    # ── Support ──────────────────────────────────────────────────────────────
    (
        ["support team", "response time", "waiting for", "no reply", "slow support", "no response"],
        "Support.Response.Delay",
    ),
]

_FALLBACK = "Support.General.Unknown"


def classify(text: str, intent: str = "complaint") -> str:
    """Return the most specific matching taxonomy path, or the fallback."""
    text_lower = text.lower()
    for keywords, path in _RULES:
        if any(kw in text_lower for kw in keywords):
            return path
    return _FALLBACK
