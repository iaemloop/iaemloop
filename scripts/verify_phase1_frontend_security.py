#!/usr/bin/env python3
"""Static security and wiring checks for the Phase 1 private dashboard."""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "js" / "privado" / "api.js"
APP = ROOT / "js" / "privado" / "app.js"
RENDER = ROOT / "js" / "privado" / "render.js"
AUTH = ROOT / "js" / "iaemloop-auth.js"
AUTH_CONFIG = ROOT / "js" / "iaemloop-auth-config.js"
HTML = ROOT / "privado" / "index.html"
LOGIN_HTML = ROOT / "area_privada.html"
CSS = ROOT / "css" / "privado-app.css"
PRIVATE_HTML_FILES = tuple(sorted((ROOT / "privado").glob("*.html")))
LEGACY_PRIVATE_HTML = (
    ROOT / "privado" / "graficos_custodia.html",
    ROOT / "privado" / "carteira_besst.html",
    ROOT / "privado" / "carteira_magic_formula.html",
    ROOT / "privado" / "carteira_besst_dolarizada.html",
    ROOT / "privado" / "carteira_magic_formula_dolarizada.html",
)
APPLICATION_FILES = tuple(dict.fromkeys(
    (API, APP, RENDER, AUTH, AUTH_CONFIG, LOGIN_HTML, CSS, *PRIVATE_HTML_FILES, *LEGACY_PRIVATE_HTML)
))
FILES = APPLICATION_FILES
TABLES = ("portfolios", "portfolio_accounts", "holdings", "portfolio_transactions")
FORBIDDEN_TOKENS = (
    "private_pages",
    "srcdoc",
    "innerHTML",
    "insertAdjacentHTML",
    "eval(",
)
LEGACY_MARKERS = ("data-private-page", "data-private-frame")
INDEX_LINK_RE = re.compile(r"href\s*=\s*['\"]index\.html(?:[?#][^'\"]*)?['\"]", re.I)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def find_forbidden_tokens(sources: dict[Path, str]) -> list[tuple[Path, str]]:
    findings: list[tuple[Path, str]] = []
    for path, text in sources.items():
        folded_text = text.casefold()
        for token in FORBIDDEN_TOKENS:
            if token.casefold() in folded_text:
                findings.append((path, token))
    return findings


def legacy_page_errors(sources: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path in LEGACY_PRIVATE_HTML:
        text = sources.get(path, "")
        relative = path.relative_to(ROOT)
        for marker in LEGACY_MARKERS:
            if marker.casefold() in text.casefold():
                errors.append(f"frontend:{relative} must not contain {marker}")
        if not INDEX_LINK_RE.search(text):
            errors.append(f"frontend:{relative} must link to index.html")
        if not re.search(r'<meta\s+name=["\']robots["\'][^>]*\bnoindex\b', text, re.I):
            errors.append(f"frontend:{relative} must be noindex")
    return errors


def password_recovery_errors(auth: str, login_html: str) -> list[str]:
    errors: list[str] = []
    auth_requirements = (
        ("event === 'PASSWORD_RECOVERY'", "recovery:must handle the Supabase PASSWORD_RECOVERY event"),
        ("sb.auth.updateUser({ password })", "recovery:must update the authenticated recovery user password"),
        ("password.length < 8", "recovery:must enforce an eight-character minimum in JavaScript"),
        ("password !== confirmation", "recovery:must require matching password confirmation"),
        ("sb.auth.signOut({ scope: 'local' })", "recovery:must end the temporary recovery session locally"),
        ("clearAuthCallbackUrl();", "recovery:must remove callback credentials/errors from the browser URL"),
        ("resetPasswordForEmail(email, { redirectTo })", "recovery:existing reset-email submission must remain wired"),
        ("error.code === 'invalid_credentials'", "recovery:login must recognize invalid credentials without exposing account existence"),
        ("use a aba Senha para redefinir o acesso", "recovery:invalid login guidance must point to the Senha tab"),
    )
    html_requirements = (
        ('id="nova-senha"', "recovery:login page must include the new-password form"),
        ('aria-labelledby="nova-senha-titulo"', "recovery:new-password form must have an accessible name"),
        ('name="password_confirmation"', "recovery:new-password form must include confirmation"),
        ('onsubmit="return IAEMLOOPAuth.updateRecoveredPassword(event)"', "recovery:new-password form must call the recovery updater"),
    )
    for marker, message in auth_requirements:
        require(marker in auth, message, errors)
    for marker, message in html_requirements:
        require(marker in login_html, message, errors)
    require(
        re.search(r"async function autoOpenIfAlreadyApproved\(\)\s*\{\s*if \(recoveryMode\) return;", auth) is not None,
        "recovery:auto-open must be synchronously blocked while recovery mode is active",
        errors,
    )
    recovery_form = re.search(r'<form class="form" id="nova-senha".*?</form>', login_html, re.S)
    require(
        bool(recovery_form and recovery_form.group(0).count('minlength="8"') == 2),
        "recovery:both new-password controls must enforce minlength eight in HTML",
        errors,
    )
    require("Login negado: " not in auth, "recovery:raw Supabase invalid-login text must not be shown", errors)
    return errors


def verify_adversarial_detection(errors: list[str], auth: str, login_html: str) -> None:
    require(Path(__file__).resolve() not in APPLICATION_FILES,
            "frontend:self-test must not scan the verifier source", errors)
    clean_sources = {path: "const phase1FrontendFixture = true;" for path in APPLICATION_FILES}
    require(bool(clean_sources), "frontend:self-test found no application files", errors)
    require(not find_forbidden_tokens(clean_sources),
            "frontend:self-test rejected clean application-file fixtures", errors)
    for path in APPLICATION_FILES:
        for token in FORBIDDEN_TOKENS:
            mutated = dict(clean_sources)
            mutated[path] = f"{mutated[path]}\n{token}"
            findings = find_forbidden_tokens(mutated)
            require((path, token) in findings,
                    f"frontend:self-test failed to reject {token} in {path.relative_to(ROOT)}", errors)

    clean_legacy = {
        path: '<meta name="robots" content="noindex"><a href="index.html">Minha Carteira</a>'
        for path in LEGACY_PRIVATE_HTML
    }
    require(not legacy_page_errors(clean_legacy),
            "frontend:self-test rejected clean legacy fixtures", errors)
    for path in LEGACY_PRIVATE_HTML:
        for marker in LEGACY_MARKERS:
            mutated = dict(clean_legacy)
            mutated[path] += marker
            require(any(marker in error and str(path.relative_to(ROOT)) in error
                        for error in legacy_page_errors(mutated)),
                    f"frontend:self-test failed to reject {marker} in {path.relative_to(ROOT)}", errors)
        mutated = dict(clean_legacy)
        mutated[path] = '<meta name="robots" content="noindex">'
        require(any("must link to index.html" in error and str(path.relative_to(ROOT)) in error
                    for error in legacy_page_errors(mutated)),
                f"frontend:self-test failed to require index link in {path.relative_to(ROOT)}", errors)

    require(not password_recovery_errors(auth, login_html),
            "recovery:self-test baseline password-recovery implementation is invalid", errors)
    recovery_mutations = (
        ("event === 'PASSWORD_RECOVERY'", "must handle the supabase password_recovery event"),
        ("sb.auth.updateUser({ password })", "must update the authenticated recovery user password"),
        ("sb.auth.signOut({ scope: 'local' })", "must end the temporary recovery session locally"),
        ("if (recoveryMode) return;", "auto-open must be synchronously blocked"),
        ('id="nova-senha"', "must include the new-password form"),
        ('name="password_confirmation"', "must include confirmation"),
    )
    for marker, expected in recovery_mutations:
        if marker in auth:
            mutated_auth, mutated_html = auth.replace(marker, "REMOVED_BY_SELF_TEST"), login_html
        elif marker in login_html:
            mutated_auth, mutated_html = auth, login_html.replace(marker, "REMOVED_BY_SELF_TEST")
        else:
            errors.append(f"recovery:self-test fixture not found: {marker}")
            continue
        messages = [message.casefold() for message in password_recovery_errors(mutated_auth, mutated_html)]
        require(any(expected in message for message in messages),
                f"recovery:self-test mutation was not rejected: {marker}", errors)


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        require(path.exists(), f"missing:{path.relative_to(ROOT)}", errors)
    if errors:
        print("PHASE1_FRONTEND_SECURITY_FAILED")
        print("\n".join(errors))
        return 1

    sources = {path: path.read_text(encoding="utf-8") for path in FILES}
    api = sources[API]
    app = sources[APP]
    render = sources[RENDER]
    auth = sources[AUTH]
    html = sources[HTML]
    login_html = sources[LOGIN_HTML]

    verify_adversarial_detection(errors, auth, login_html)
    errors.extend(password_recovery_errors(auth, login_html))
    for path, token in find_forbidden_tokens(sources):
        errors.append(f"frontend:{path.relative_to(ROOT)} must not contain {token}")
    errors.extend(legacy_page_errors(sources))

    config = sources[AUTH_CONFIG]
    require("requireApprovedSession" in auth and "getApprovedSession" in auth, "frontend:auth must expose live approved-session validation", errors)
    require("scheduleIdleExpiry" in auth and "setTimeout" in auth and "iaemloop:session-invalidated" in auth,
            "frontend:auth must enforce idle expiry while the page remains open", errors)
    require("clearApprovedUi" in auth and "signOut" in auth and "window.location.replace" in auth,
            "frontend:expiry must clear/lock private UI, sign out, and redirect", errors)
    require("configIssue" in auth and "key.length < 80" in auth and "key.startsWith('sb_secret_')" in auth,
            "frontend:auth config validation must reject placeholders, truncation, and privileged keys", errors)
    require("ACTIVITY_WRITE_INTERVAL_MS" in auth and "lastActivityMemory" in auth,
            "frontend:activity must extend the live timer without relying on stale persisted timestamps", errors)
    require("event.newValue === null" in auth and "reason: 'signed-out'" in auth,
            "frontend:cross-tab logout must invalidate and clear visible private data", errors)
    require("freshContext" in api and "requireApprovedSession" in api,
            "frontend:every structured API operation must obtain a fresh approved context", errors)
    require(".eq('user_id', context.user.id)" in api, "frontend:queries/deletes need explicit user filter", errors)
    require("user_id: context.user.id" in api, "frontend:inserts must bind user_id to authenticated user", errors)
    require(api.count(".eq('user_id', context.user.id)") >= 2, "frontend:list and delete paths both need user filter", errors)

    for table in TABLES:
        require(f"'{table}'" in api, f"frontend:missing structured API for {table}", errors)

    require("textContent" in app, "frontend:app must render user/database text via textContent", errors)
    require("document.createTextNode" in render, "frontend:renderer must create text nodes", errors)
    require("replaceChildren" in app, "frontend:tables/selects must replace DOM safely", errors)
    require("window.confirm" in app, "frontend:destructive deletes need confirmation", errors)
    require(app.count("await currentContext()") >= 4,
            "frontend:refresh/create/delete/start paths must revalidate the approved session", errors)
    require("clearPrivateState" in app and "iaemloop:session-invalidated" in app,
            "frontend:app must erase rendered private state when the session is invalidated", errors)
    require("isTrade && (!(quantity > 0) || !(unitPrice > 0))" in app,
            "frontend:buy/sell must require positive quantity and unit price", errors)
    require("isTrade && !symbol" in app,
            "frontend:buy/sell must require a nonempty ticker", errors)
    require("syncTransactionRequirements" in app and "['symbol', 'quantity', 'unit_price']" in app
            and "input.required = isTrade" in app,
            "frontend:ticker, quantity, and unit price requirements must follow buy/sell selection", errors)

    require("..." not in config and "SUA_ANON_PUBLIC_KEY" not in config,
            "frontend:auth config must not contain a placeholder/truncated browser key", errors)
    key_match = re.search(r"supabaseAnonKey\s*:\s*[\"']([^\"']+)", config)
    require(bool(key_match and (
        (key_match.group(1).startswith("eyJ") and len(key_match.group(1)) >= 80)
        or (key_match.group(1).startswith("sb_publishable_") and len(key_match.group(1)) >= 30)
    )),
            "frontend:auth config must contain a complete public browser key", errors)
    require("service_role" not in config.casefold() and "sb_secret_" not in config,
            "frontend:auth config must not contain a privileged key", errors)
    url_match = re.search(r"supabaseUrl\s*:\s*[\"']https://([a-z0-9]+)\.supabase\.co", config, re.I)
    if key_match and url_match and key_match.group(1).count(".") == 2:
        try:
            encoded = key_match.group(1).split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            require(payload.get("role") in {"anon", "publishable"},
                    "frontend:browser JWT must have an anon/publishable role", errors)
            require(payload.get("ref") == url_match.group(1),
                    "frontend:browser JWT must belong to the configured Supabase project", errors)
        except (ValueError, json.JSONDecodeError):
            errors.append("frontend:browser JWT payload must be valid")

    for script in ("../js/privado/api.js", "../js/privado/render.js", "../js/privado/app.js"):
        require(script in html, f"frontend:index missing script {script}", errors)
    for marker in ("data-form=\"portfolio\"", "data-form=\"account\"", "data-form=\"holding\"", "data-form=\"transaction\""):
        require(marker in html, f"frontend:index missing form {marker}", errors)
    require("data-requires-approved-user" in html, "frontend:index must retain approved-user gate", errors)
    require("id=\"private-app\"" in html, "frontend:index missing private app root", errors)
    require("aria-live=\"assertive\"" in html and "aria-live=\"polite\"" in html,
            "frontend:auth and application statuses must be live regions", errors)
    require("@supabase/supabase-js@2.117.2" in html,
            "frontend:Supabase CDN dependency must be pinned to the reviewed exact version", errors)
    require("<label>" not in html, "frontend:Phase 1 form labels must have explicit associations", errors)
    require("id=\"transaction-quantity\"" in html and "id=\"transaction-unit-price\"" in html,
            "frontend:trade quantity/unit price controls must be explicitly labelled", errors)
    require("<label>" not in login_html and "aria-live=\"polite\"" in login_html,
            "frontend:login forms need associated labels and a live status region", errors)
    for path in ROOT.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "@supabase/supabase-js@" in text:
            require("@supabase/supabase-js@2.117.2" in text and "@supabase/supabase-js@2\"" not in text,
                    f"frontend:{path.name} must pin the reviewed Supabase JS version", errors)

    require(re.search(r"\.from\(table\).*?\.eq\('user_id', context\.user\.id\)", api, re.S) is not None,
            "frontend:generic read must filter user_id", errors)
    require(re.search(r"\.delete\(\).*?\.eq\('id', id\).*?\.eq\('user_id', context\.user\.id\)", api, re.S) is not None,
            "frontend:delete must constrain id and user_id", errors)

    if errors:
        print("PHASE1_FRONTEND_SECURITY_FAILED")
        for error in errors:
            print(error)
        return 1
    print("PHASE1_FRONTEND_SECURITY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
