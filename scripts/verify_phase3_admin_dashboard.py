#!/usr/bin/env python3
"""Adversarial static verifier for the Phase 3 admin access dashboard."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase" / "phase3-admin-access-dashboard.sql"
AUTH = ROOT / "js" / "iaemloop-auth.js"
AUTH_CONFIG = ROOT / "js" / "iaemloop-auth-config.js"
LOGIN_HTML = ROOT / "area_privada.html"
INDEX = ROOT / "privado" / "index.html"
PORTFOLIO_HTML = ROOT / "privado" / "minha-carteira.html"
GRAPHICS = ROOT / "privado" / "graficos_custodia.html"
ADMIN_HTML = ROOT / "privado" / "admin-acessos.html"
ADMIN_JS = ROOT / "js" / "privado" / "admin-access.js"
ADMIN_NAV = ROOT / "js" / "privado" / "admin-nav.js"
CSS = ROOT / "css" / "privado-app.css"
PRIVATE_HTML_FILES = tuple(sorted((ROOT / "privado").glob("*.html")))
PRIVATE_JS_FILES = tuple(sorted((ROOT / "js" / "privado").glob("*.js")))
ACCESS_HTML_FILES = tuple(sorted(ROOT.glob("*_acesso.html")))
BROWSER_FILES = tuple(dict.fromkeys((AUTH, AUTH_CONFIG, LOGIN_HTML, *ACCESS_HTML_FILES, *PRIVATE_HTML_FILES, *PRIVATE_JS_FILES)))
PRIVATE_AUTHORIZATION_FILES = tuple(dict.fromkeys((*PRIVATE_HTML_FILES, *PRIVATE_JS_FILES)))
FILES = tuple(dict.fromkeys((SQL, CSS, *BROWSER_FILES)))
RPCS = {
    "admin_is_current_user": "",
    "admin_list_access_requests": "text, text, integer, integer",
    "admin_set_access_status": "uuid, text, text, text",
}
FORBIDDEN_BROWSER_TOKENS = ("innerHTML", "insertAdjacentHTML", "srcdoc", "eval(", "private_pages", "diegoremmurd@gmail.com", "diegoremmurd@hotmail.com")
OWNER_EMAIL_TOKENS = ("equipeiaemloop@gmail.com", "diegoremmurd@gmail.com", "diegoremmurd@hotmail.com")
USER_EMAIL_AUTH_RE = re.compile(
    r"(?:\bif\s*\([^;\n]*(?:(?:context|session)\.)?user\??\.email\b|"
    r"\b(?:(?:context|session)\.)?user\??\.email\b[^;\n]*(?:===?|!==?|\.includes\(|\.has\())",
    re.I,
)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def strip_sql_comments(sql: str) -> str:
    output: list[str] = []
    index = 0
    quote: str | None = None
    dollar_tag: str | None = None
    block_depth = 0
    while index < len(sql):
        if block_depth:
            if sql.startswith("/*", index):
                block_depth += 1
                index += 2
            elif sql.startswith("*/", index):
                block_depth -= 1
                index += 2
            else:
                if sql[index] == "\n":
                    output.append("\n")
                index += 1
            continue
        if dollar_tag:
            if sql.startswith(dollar_tag, index):
                output.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
            else:
                output.append(sql[index])
                index += 1
            continue
        if quote:
            output.append(sql[index])
            if sql[index] == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            if newline == -1:
                break
            output.append("\n")
            index = newline + 1
            continue
        if sql.startswith("/*", index):
            block_depth = 1
            index += 2
            continue
        if sql[index] in ("'", '"'):
            quote = sql[index]
            output.append(sql[index])
            index += 1
            continue
        if sql[index] == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                output.append(dollar_tag)
                index += len(dollar_tag)
                continue
        output.append(sql[index])
        index += 1
    return "".join(output)


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def executable_sql(raw: str) -> str:
    return compact(strip_sql_comments(raw))


def function_definitions(raw: str, name: str) -> list[str]:
    clean = strip_sql_comments(raw)
    pattern = re.compile(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(name)}\s*\(.*?"
        rf"as\s+(\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$)(.*?)\1\s*;",
        re.I | re.S,
    )
    return [compact(match.group(0)) for match in pattern.finditer(clean)]


def final_function(raw: str, name: str) -> str:
    definitions = function_definitions(raw, name)
    return definitions[-1] if definitions else ""


def block_body(raw: str, tag: str) -> str:
    clean = strip_sql_comments(raw)
    match = re.search(rf"do\s+\${re.escape(tag)}\$(.*?)\${re.escape(tag)}\$\s*;", clean, re.I | re.S)
    return compact(match.group(1)) if match else ""


def has_weak_boolean(body: str) -> bool:
    return bool(re.search(r"\bor\s+(?:pg_catalog\.)?true\b|\b(?:pg_catalog\.)?true\s+or\b", body, re.I))


def sql_errors(raw: str) -> list[str]:
    errors: list[str] = []
    sql = executable_sql(raw)
    require(sql.startswith("begin;"), "sql:migration must begin a transaction", errors)
    require(sql.endswith("commit;"), "sql:migration must commit the transaction", errors)

    catalog = block_body(raw, "phase3_catalog_preflight")
    definitions = block_body(raw, "phase3_definition_preflight")
    identity = block_body(raw, "phase3_audit_identity_reconcile")
    keys = block_body(raw, "phase3_key_reconcile")
    require("to_regclass('auth.users') is null" in catalog and "to_regclass('public.access_requests') is null" in catalog,
            "sql:catalog preflight must fail closed when required deployed relations are absent", errors)
    for marker in (
        "null user_id requires manual repair", "duplicate user_id requires manual repair",
        "orphan user_id requires manual repair", "null actor_user_id requires manual repair",
        "null target_user_id requires manual repair", "invalid previous_status requires manual repair",
        "invalid new_status requires manual repair", "unchanged status rows require manual repair",
        "overlong reason requires manual repair", "orphan actor_user_id requires manual repair",
        "orphan target_user_id requires manual repair", "conflicting primary key requires manual repair",
    ):
        require(marker in definitions, f"sql:definition preflight missing fail-closed check: {marker}", errors)
    require("data_type <> 'uuid'" in definitions and "data_type <> 'bigint'" in definitions and "data_type <> 'timestamp with time zone'" in definitions,
            "sql:definition preflight must reject incompatible existing column types", errors)

    require("alter column user_id set not null" in sql and "alter column created_at set default pg_catalog.now()" in sql,
            "sql:admin_members must reconcile NOT NULL/default definitions", errors)
    require("alter column actor_user_id set not null" in sql and "alter column target_user_id set not null" in sql,
            "sql:audit actor and target must reconcile to NOT NULL", errors)
    require("alter column previous_status set not null" in sql and "alter column new_status set not null" in sql and "alter column decided_at set not null" in sql,
            "sql:audit status/timestamp columns must reconcile to NOT NULL", errors)
    require("add generated always as identity" in identity and "set generated always" in identity and "pg_get_serial_sequence" in identity and "setval" in identity,
            "sql:audit id must reconcile to GENERATED ALWAYS identity without discarding legacy rows", errors)

    for marker in (
        "admin_members_pkey primary key (user_id)",
        "access_status_audit_pkey primary key (id)",
        "foreign key (user_id) references auth.users(id) on delete cascade",
        "foreign key (created_by) references auth.users(id) on delete set null",
        "foreign key (actor_user_id) references auth.users(id) on delete restrict",
        "foreign key (target_user_id) references auth.users(id) on delete restrict",
        "conflicting foreign key requires manual repair",
    ):
        require(marker in keys, f"sql:key reconciliation missing: {marker}", errors)
    for marker in (
        "access_status_audit_previous_status_check check (previous_status in ('pending', 'approved', 'rejected'))",
        "access_status_audit_new_status_check check (new_status in ('pending', 'approved', 'rejected'))",
        "access_status_audit_status_changed_check check (previous_status <> new_status)",
        "access_status_audit_reason_length_check check (reason is null or pg_catalog.length(reason) <= 500)",
        "create index phase3_admin_members_created_by_idx",
        "create index phase3_access_status_audit_target_decided_idx",
        "create index phase3_access_status_audit_actor_decided_idx",
    ):
        require(marker in sql, f"sql:missing reconciled check/index: {marker}", errors)

    require("force row level security" in sql and "phase3_drop_private_policies" in sql,
            "sql:private tables must force RLS and remove stale policies", errors)
    for table in ("private.admin_members", "private.access_status_audit"):
        for role in ("public", "anon", "authenticated"):
            require(f"revoke all on table {table} from {role};" in sql, f"sql:{table} must revoke {role}", errors)
        direct_grants = re.findall(rf"grant\s+[^;]*on\s+table\s+{re.escape(table)}\s+to\s+[^;]+;", sql, re.I)
        require(not direct_grants, f"sql:{table} must have no direct grants", errors)

    require("before update or delete on private.access_status_audit" in sql and "before truncate on private.access_status_audit" in sql,
            "sql:audit table must reject UPDATE, DELETE, and TRUNCATE", errors)

    bootstrap = block_body(raw, "phase3_admin_bootstrap")
    require("where pg_catalog.lower(u.email) = 'diegoremmurd@gmail.com'" in bootstrap and "if bootstrap_count <> 1 then" in bootstrap,
            "sql:Gmail bootstrap must resolve exactly one immutable Auth user", errors)
    require("on conflict (user_id) do nothing" in bootstrap and "delete from private.admin_members as am where am.user_id <> bootstrap_user_id" not in bootstrap,
            "sql:bootstrap must add Gmail without replacing unrelated admins", errors)
    require("equipeiaemloop@gmail.com" not in bootstrap,
            "sql:bootstrap must not permanently exclude the management email", errors)
    require("where pg_catalog.lower(u.email) = 'diegoremmurd@hotmail.com'" in bootstrap and "if ordinary_count <> 1 then" in bootstrap,
            "sql:Hotmail bootstrap must resolve exactly one immutable Auth user", errors)
    require("delete from private.admin_members as am where am.user_id = ordinary_user_id" in bootstrap,
            "sql:Hotmail user must be approved but removed from admin membership", errors)
    require("values (ordinary_user_id, ordinary_email, ordinary_name, 'approved', 'user'" in bootstrap,
            "sql:Hotmail bootstrap must retain approved ordinary-user access", errors)
    require(bootstrap.count("when exists (select 1 from private.admin_members as am where am.user_id = ar.user_id) then 'admin'") == 2,
            "sql:stored role synchronization must derive all admins from membership", errors)

    for name, args in RPCS.items():
        definitions_for_rpc = function_definitions(raw, name)
        body = definitions_for_rpc[-1] if definitions_for_rpc else ""
        require(len(definitions_for_rpc) == 1, f"sql:{name} must have exactly one executable final definition", errors)
        require("security definer" in body and "set search_path = ''" in body,
                f"sql:{name} must be SECURITY DEFINER with empty search_path", errors)
        require("private.admin_members" in body and "auth.uid()" in body,
                f"sql:{name} must authorize by current UUID membership", errors)
        require(not has_weak_boolean(body), f"sql:{name} contains a weakened OR TRUE predicate", errors)
        signature = f"public.{name}({args})" if args else f"public.{name}()"
        for role in ("public", "anon", "authenticated"):
            require(f"revoke all on function {signature} from {role};" in sql, f"sql:{name} must revoke {role}", errors)
        require(sql.count(f"grant execute on function {signature} to authenticated;") == 1,
                f"sql:{name} must grant EXECUTE exactly once to authenticated", errors)
        require(not re.search(rf"grant\s+execute\s+on\s+function\s+{re.escape(signature)}\s+to\s+(?:public|anon)\s*;", sql, re.I),
                f"sql:{name} must not grant EXECUTE to public/anon", errors)

    is_admin = final_function(raw, "admin_is_current_user")
    require("where am.user_id = (select auth.uid())" in is_admin,
            "sql:admin_is_current_user must use exact UUID membership", errors)
    list_body = final_function(raw, "admin_list_access_requests")
    require("returns jsonb" in list_body and "'filtered_count'" in list_body and "'items'" in list_body and "'counts'" in list_body,
            "sql:list RPC must return paginated items, exact filtered count, and global counters", errors)
    require("bounded_offset := greatest(coalesce(p_offset, 0), 0)" in list_body and "limit bounded_limit offset bounded_offset" in list_body,
            "sql:list RPC must support usable untruncated offset pagination", errors)
    require("case when am.user_id is not null then 'admin'::text else 'user'::text end as role" in list_body,
            "sql:list RPC role must be derived live from admin_members", errors)
    require("left join private.admin_members as am on am.user_id = ar.user_id" in list_body,
            "sql:list RPC must join authoritative admin membership", errors)

    set_body = final_function(raw, "admin_set_access_status")
    require("p_target_user_id = caller_id" in set_body and "am.user_id = p_target_user_id" in set_body,
            "sql:status RPC must block self and administrator targets", errors)
    require("for update" in set_body and "ar.status = normalized_expected" in set_body,
            "sql:status RPC must lock and compare the expected status", errors)
    require("insert into private.access_status_audit" in set_body,
            "sql:status RPC must audit in the same transaction", errors)
    require("case when am.user_id is not null then 'admin'::text else 'user'::text end" in set_body,
            "sql:status RPC must return role from live admin membership", errors)
    return errors


def browser_errors(sources: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path in BROWSER_FILES:
        folded = sources[path].casefold()
        for token in FORBIDDEN_BROWSER_TOKENS:
            require(token.casefold() not in folded, f"browser:{path.relative_to(ROOT)} must not contain {token}", errors)
        require(re.search(r"sb_secret_[a-z0-9]{12,}", folded) is None,
                f"browser:{path.relative_to(ROOT)} must not contain a service key", errors)
    for path in PRIVATE_AUTHORIZATION_FILES:
        folded = sources[path].casefold()
        for token in OWNER_EMAIL_TOKENS:
            require(token.casefold() not in folded, f"browser:{path.relative_to(ROOT)} must not contain owner email {token}", errors)
        require(USER_EMAIL_AUTH_RE.search(sources[path]) is None,
                f"browser:{path.relative_to(ROOT)} must not authorize from browser user email", errors)

    admin_js = sources[ADMIN_JS]
    admin_html = sources[ADMIN_HTML]
    nav = sources[ADMIN_NAV]
    index = sources[INDEX]
    auth = sources[AUTH]
    start_body = admin_js[admin_js.find("async function start()") :]
    require("requireApprovedSession" in admin_js and start_body.find("rpc('admin_is_current_user')") < start_body.find("await refresh()"),
            "browser:admin UUID-membership check must precede record loading", errors)
    require("if (isAdmin !== true) return denyAdmin();" in admin_js and "window.location.replace('index.html')" in admin_js,
            "browser:ordinary users must be denied and redirected", errors)
    require("PAGE_SIZE = 50" in admin_js and "p_offset: requestedPage * PAGE_SIZE" in admin_js,
            "browser:list integration must send real page offsets", errors)
    require("admin-page-previous" in admin_html and "admin-page-next" in admin_html and "admin-page-range" in admin_html,
            "browser:admin page must expose previous/next controls and exact range", errors)
    require("page = 0" in admin_js and "resetPageAndRefresh" in admin_js,
            "browser:filter/search changes must reset pagination", errors)
    require("filteredCount" in admin_js and "Exibindo ${first}–${last} de ${state.filteredCount}" in admin_js,
            "browser:shown range must use exact filtered count", errors)
    require("refreshGeneration" in admin_js and "generation !== refreshGeneration" in admin_js,
            "browser:stale refresh responses must not repaint the table", errors)
    require("Decisão registrada e auditada, mas a atualização da lista falhou" in admin_js and "reconcileMutation(updatedItem," in admin_js,
            "browser:mutation success must remain distinct from refresh failure and reconcile returned data", errors)
    require("row.querySelectorAll('button')" in admin_js and "element.disabled = true" in admin_js,
            "browser:the affected row must be disabled during mutation", errors)
    require("window.confirm" in admin_js and "['reject', 'revoke']" in admin_js,
            "browser:reject and revoke actions must require confirmation", errors)
    require("document.createElement" in admin_js and "textContent" in admin_js,
            "browser:admin UI must use safe DOM creation", errors)
    for counter in ("pending", "approved", "rejected", "total"):
        require(f'id="admin-count-{counter}"' in admin_html, f"browser:missing {counter} counter", errors)
    require('data-requires-approved-user' in admin_html and 'id="admin-app" hidden' in admin_html,
            "browser:admin records must remain hidden until both gates pass", errors)
    require('maxlength="120"' in admin_html, "browser:search input must match RPC bound", errors)
    require("data-admin-entry hidden" in index and 'href="admin-acessos.html"' in index,
            "browser:private hub needs a hidden conditional admin entry", errors)
    require("rpc('admin_is_current_user')" in nav and "data === true" in nav and "entry.hidden = false" in nav,
            "browser:admin entry must be revealed only by the admin RPC", errors)
    require("approvedSessionPromise" in auth and "getApprovedSessionShared" in auth,
            "browser:concurrent private navigation checks must coalesce duplicate session fetches", errors)
    custody_routes = (
        "carteira_besst.html",
        "carteira_magic_formula.html",
        "carteira_besst_dolarizada.html",
        "carteira_magic_formula_dolarizada.html",
    )
    require(all(route in index and route in sources[PORTFOLIO_HTML] for route in custody_routes)
            and "Minhas 4 carteiras em custódia" in sources[PORTFOLIO_HTML],
            "browser:hub and Minha Carteira must preserve direct access to all four custody routes", errors)
    return errors


def run_mutation_tests(sql_raw: str, sources: dict[Path, str]) -> list[str]:
    failures: list[str] = []

    def expect_sql_rejection(label: str, mutated: str, expected: str) -> None:
        messages = [message.casefold() for message in sql_errors(mutated)]
        if not any(expected.casefold() in message for message in messages):
            failures.append(f"self-test:{label} mutation was not rejected")

    replacements = (
        ("OR TRUE admin predicate", "where am.user_id = (select auth.uid())", "where am.user_id = (select auth.uid()) or true", "weakened or true"),
        ("nullable audit actor", "alter column actor_user_id set not null", "alter column actor_user_id drop not null", "actor and target must reconcile to not null"),
        ("missing legacy-null preflight", "NULL actor_user_id requires manual repair", "actor may be null", "definition preflight missing"),
        ("offset cap", "bounded_offset := greatest(coalesce(p_offset, 0), 0)", "bounded_offset := least(greatest(coalesce(p_offset, 0), 0), 200)", "usable untruncated offset pagination"),
        ("stored role trust", "case when am.user_id is not null then 'admin'::text else 'user'::text end as role", "ar.role", "role must be derived live"),
        ("Hotmail admin removal", "delete from private.admin_members as am where am.user_id = ordinary_user_id", "delete from private.admin_members as am where am.user_id = bootstrap_user_id", "hotmail user must be approved but removed"),
    )
    for label, old, new, expected in replacements:
        if old not in sql_raw:
            failures.append(f"self-test:{label} fixture not found")
        else:
            expect_sql_rejection(label, sql_raw.replace(old, new, 1), expected)

    appended_grant = sql_raw + "\ngrant execute on function public.admin_is_current_user() to anon;\n"
    expect_sql_rejection("appended anon grant", appended_grant, "must not grant execute to public/anon")

    final_is_admin = final_function(sql_raw, "admin_is_current_user")
    if not final_is_admin:
        failures.append("self-test:final admin function fixture not found")
    else:
        weak_definition = re.sub(r"where am\.user_id = \(select auth\.uid\(\)\)", "where am.user_id = (select auth.uid()) or true", final_is_admin, count=1)
        expect_sql_rejection("appended weakened function", sql_raw + "\n" + weak_definition + "\n", "exactly one executable final definition")

    mutated_sources = dict(sources)
    mutated_sources[ADMIN_JS] = sources[ADMIN_JS] + "\nelement.innerHTML = unsafeValue;\n"
    if not any("innerhtml" in message.casefold() for message in browser_errors(mutated_sources)):
        failures.append("self-test:unsafe HTML sink was not rejected")

    browser_mutations = (
        ("pagination offset", ADMIN_JS, "p_offset: requestedPage * PAGE_SIZE", "p_offset: 0", "real page offsets"),
        ("refresh generation", ADMIN_JS, "generation !== refreshGeneration", "generation === refreshGeneration", "stale refresh responses"),
        ("mutation refresh honesty", ADMIN_JS, "Decisão registrada e auditada, mas a atualização da lista falhou", "Não foi possível registrar a decisão", "mutation success must remain distinct"),
        ("filter page reset", ADMIN_JS, "resetPageAndRefresh", "refreshWithoutReset", "filter/search changes must reset"),
    )
    for label, path, old, new, expected in browser_mutations:
        if old not in sources[path]:
            failures.append(f"self-test:{label} fixture not found")
            continue
        mutated_sources = dict(sources)
        mutated_sources[path] = sources[path].replace(old, new)
        if not any(expected in message.casefold() for message in browser_errors(mutated_sources)):
            failures.append(f"self-test:{label} mutation was not rejected")

    for path in PRIVATE_AUTHORIZATION_FILES:
        mutated_sources = dict(sources)
        mutated_sources[path] = sources[path] + "\nconst ownerOnly = 'equipeiaemloop@gmail.com';\n"
        messages = [message.casefold() for message in browser_errors(mutated_sources)]
        if not any("must not contain owner email equipeiaemloop@gmail.com" in message and str(path.relative_to(ROOT)).casefold() in message for message in messages):
            failures.append(f"self-test:owner email mutation was not rejected in {path.relative_to(ROOT)}")

    mutated_sources = dict(sources)
    mutated_sources[GRAPHICS] = sources[GRAPHICS] + "\nif (context.user.email) grantCustodyAccess();\n"
    if not any("must not authorize from browser user email" in message.casefold() for message in browser_errors(mutated_sources)):
        failures.append("self-test:browser user-email authorization mutation was not rejected")
    return failures


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        require(path.exists(), f"missing:{path.relative_to(ROOT)}", errors)
    if errors:
        print("PHASE3_ADMIN_DASHBOARD_FAILED")
        print("\n".join(errors))
        return 1
    sources = {path: path.read_text(encoding="utf-8") for path in FILES}
    errors.extend(sql_errors(sources[SQL]))
    errors.extend(browser_errors(sources))
    errors.extend(run_mutation_tests(sources[SQL], sources))
    if errors:
        print("PHASE3_ADMIN_DASHBOARD_FAILED")
        for error in errors:
            print(error)
        return 1
    print("PHASE3_ADMIN_DASHBOARD_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
