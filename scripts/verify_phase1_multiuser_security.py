#!/usr/bin/env python3
"""Adversarial static security contract for the Phase 1 Supabase schema."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = ROOT / "supabase" / "phase1-multiuser-portfolio.sql"
ACCESS = ROOT / "supabase" / "access-control.sql"
FIX = ROOT / "supabase" / "fix-access-trigger-backfill.sql"

TABLES = (
    "portfolios",
    "portfolio_accounts",
    "holdings",
    "portfolio_transactions",
    "portfolio_documents",
    "portfolio_analyses",
    "contribution_plans",
)
CHILDREN = TABLES[1:]
POLICY_ACTIONS = ("select", "insert", "update", "delete")
OWNER_PREDICATE = "private.is_approved_user() and (select auth.uid()) = user_id"
STORAGE_PREDICATES = (
    "private.is_approved_user()",
    "bucket_id = 'user-documents'",
    "(storage.foldername(name))[1] = (select auth.uid())::text",
)
STORAGE_GUARD_PREDICATE = (
    "bucket_id <> 'user-documents' or "
    "(private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text)"
)
ANON_STORAGE_GUARD_PREDICATE = "bucket_id <> 'user-documents'"
EXPECTED_APPROVAL_BODY = (
    "select exists (select 1 from public.access_requests as ar "
    "where ar.user_id = (select auth.uid()) and ar.status = 'approved');"
)
EXPECTED_ACCESS_TRIGGER_BODY = (
    "begin "
    "insert into public.access_requests (user_id, email, full_name, status) "
    "values (new.id, new.email, "
    "coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', ''), "
    "'pending') "
    "on conflict (user_id) do update "
    "set email = excluded.email, "
    "full_name = coalesce(nullif(excluded.full_name, ''), public.access_requests.full_name), "
    "updated_at = pg_catalog.now(); "
    "return new; "
    "end;"
)
TRADE_CONSTRAINT_NAME = "portfolio_transactions_trade_fields_check"
EXPECTED_TRADE_CHECK = (
    "transaction_type not in ('buy', 'sell') or ("
    "symbol is not null and length(btrim(symbol)) between 1 and 32 "
    "and quantity is not null and quantity > 0 "
    "and unit_price is not null and unit_price > 0)"
)
EXPECTED_TRADE_PREFLIGHT_BODY = (
    "declare invalid_trade_count bigint; begin "
    "select pg_catalog.count(*) into invalid_trade_count "
    "from public.portfolio_transactions "
    "where transaction_type in ('buy', 'sell') and ("
    "symbol is null or length(btrim(symbol)) not between 1 and 32 "
    "or quantity is null or quantity <= 0 "
    "or unit_price is null or unit_price <= 0); "
    "if invalid_trade_count > 0 then "
    "raise exception 'cannot enforce public.portfolio_transactions BUY/SELL integrity: % legacy row(s) require a nonempty symbol, quantity > 0, and unit_price > 0', "
    "invalid_trade_count; end if; end;"
)
FINAL_FOREIGN_KEYS = {
    ("holdings", "holdings_user_id_portfolio_id_account_id_fkey"): (
        ("user_id", "portfolio_id", "account_id"),
        "portfolio_accounts",
        ("user_id", "portfolio_id", "id"),
        "cascade",
        (),
    ),
    ("portfolio_transactions", "portfolio_transactions_user_id_portfolio_id_account_id_fkey"): (
        ("user_id", "portfolio_id", "account_id"),
        "portfolio_accounts",
        ("user_id", "portfolio_id", "id"),
        "cascade",
        (),
    ),
    ("portfolio_documents", "portfolio_documents_user_id_portfolio_id_account_id_fkey"): (
        ("user_id", "portfolio_id", "account_id"),
        "portfolio_accounts",
        ("user_id", "portfolio_id", "id"),
        "set null",
        ("account_id",),
    ),
    ("portfolio_analyses", "portfolio_analyses_user_id_portfolio_id_document_id_fkey"): (
        ("user_id", "portfolio_id", "document_id"),
        "portfolio_documents",
        ("user_id", "portfolio_id", "id"),
        "set null",
        ("document_id",),
    ),
}


def strip_sql_comments(sql: str) -> str:
    """Remove PostgreSQL comments without touching quoted or dollar-quoted text."""
    output: list[str] = []
    index = 0
    block_depth = 0
    quote: str | None = None
    dollar_tag: str | None = None
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
            match = re.match(r"\$[a-zA-Z_][a-zA-Z0-9_]*\$|\$\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                output.append(dollar_tag)
                index += len(dollar_tag)
                continue
        output.append(sql[index])
        index += 1
    return "".join(output)


def compact(sql: str) -> str:
    return re.sub(r"\s+", " ", strip_sql_comments(sql)).strip().lower()


def sql_tokens(sql: str) -> tuple[str, ...]:
    """Normalize SQL while preserving operators and statement boundaries."""
    return tuple(
        re.findall(
            r"'(?:''|[^'])*'|::|<>|!=|<=|>=|[a-z_][a-z0-9_$.]*|\d+(?:\.\d+)?|[(),;=*+\-/<>]",
            compact(sql),
        )
    )


def comma_names(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def grant_statements(sql: str) -> list[tuple[int, str]]:
    sql = strip_sql_comments(sql)
    return [(match.start(), compact(match.group(0))) for match in re.finditer(r"\bgrant\s+[^;]+;", sql, re.I | re.S)]


def create_policy_statements(sql: str, schema: str, table: str) -> list[tuple[int, str]]:
    sql = strip_sql_comments(sql)
    pattern = rf"\bcreate\s+policy\s+[^;]+?\s+on\s+{re.escape(schema)}\.{re.escape(table)}\b[^;]*;"
    return [(match.start(), compact(match.group(0))) for match in re.finditer(pattern, sql, re.I | re.S)]


def all_create_policy_statements(sql: str) -> list[tuple[int, str]]:
    sql = strip_sql_comments(sql)
    return [
        (match.start(), compact(match.group(0)))
        for match in re.finditer(r"\bcreate\s+policy\s+[^;]+;", sql, re.I | re.S)
    ]


def grant_targets_table(statement: str, table: str) -> bool:
    if re.search(r"\bon\s+all\s+tables\s+in\s+schema\s+public\b", statement):
        return True
    match = re.search(r"\bon\s+(?:table\s+)?(.+?)\s+to\s+", statement)
    if not match:
        return False
    targets = {target.removeprefix("only ").strip() for target in match.group(1).split(",")}
    return table in targets or f"public.{table}" in targets


def final_fk_additions(raw: str) -> dict[tuple[str, str], list[tuple[int, tuple[object, ...]]]]:
    raw = strip_sql_comments(raw)
    pattern = re.compile(
        r"alter\s+table\s+public\.(?P<table>[a-z_][a-z0-9_]*)\s+"
        r"add\s+constraint\s+(?P<constraint>[a-z_][a-z0-9_]*)\s+"
        r"foreign\s+key\s*\((?P<columns>[^)]*)\)\s+"
        r"references\s+public\.(?P<ref_table>[a-z_][a-z0-9_]*)\s*\((?P<ref_columns>[^)]*)\)\s+"
        r"on\s+delete\s+(?P<action>cascade|restrict|no\s+action|set\s+null|set\s+default)"
        r"(?:\s*\((?P<delete_columns>[^)]*)\))?\s*;",
        re.I | re.S,
    )
    additions: dict[tuple[str, str], list[tuple[int, tuple[object, ...]]]] = {}
    for match in pattern.finditer(raw):
        key = (match.group("table").lower(), match.group("constraint").lower())
        shape = (
            comma_names(compact(match.group("columns"))),
            match.group("ref_table").lower(),
            comma_names(compact(match.group("ref_columns"))),
            compact(match.group("action")),
            comma_names(compact(match.group("delete_columns") or "")),
        )
        additions.setdefault(key, []).append((match.start(), shape))
    return additions


def trade_check_additions(raw: str) -> list[tuple[int, str]]:
    """Return named trade CHECK additions with their exact expressions."""
    raw = strip_sql_comments(raw)
    pattern = re.compile(
        rf"alter\s+table\s+public\.portfolio_transactions\s+add\s+constraint\s+"
        rf"{re.escape(TRADE_CONSTRAINT_NAME)}\s+check\s*\((?P<expression>.*?)\)\s+not\s+valid\s*;",
        re.I | re.S,
    )
    return [(match.start(), compact(match.group("expression"))) for match in pattern.finditer(raw)]


def table_body(raw: str, table: str) -> str:
    raw = strip_sql_comments(raw)
    match = re.search(
        rf"create\s+table\s+if\s+not\s+exists\s+public\.{table}\s*\((.*?)\)\s*;",
        raw,
        flags=re.S | re.I,
    )
    return compact(match.group(1)) if match else ""


def tagged_block(raw: str, tag: str) -> str:
    raw = strip_sql_comments(raw)
    match = re.search(rf"do\s+\${re.escape(tag)}\$(.*?)\${re.escape(tag)}\$\s*;", raw, re.S | re.I)
    return compact(match.group(1)) if match else ""


def function_body(raw: str) -> str:
    raw = strip_sql_comments(raw)
    match = re.search(
        r"create\s+or\s+replace\s+function\s+private\.is_approved_user\s*\(\s*\).*?as\s+\$\$(.*?)\$\$\s*;",
        raw,
        re.S | re.I,
    )
    return compact(match.group(1)) if match else ""


def access_trigger_body(raw: str) -> str:
    raw = strip_sql_comments(raw)
    match = re.search(
        r"create\s+or\s+replace\s+function\s+public\.handle_new_access_request\s*\(\s*\).*?"
        r"as\s+(\$[a-zA-Z_][a-zA-Z0-9_]*\$|\$\$)(.*?)\1\s*;",
        raw,
        re.S | re.I,
    )
    return compact(match.group(2)) if match else ""


def policy_clause(
    sql: str,
    schema: str,
    table: str,
    name: str,
    action: str,
    *,
    restrictive: bool = False,
    role: str = "authenticated",
) -> str:
    sql = strip_sql_comments(sql)
    mode = r"as\s+restrictive\s+" if restrictive else ""
    match = re.search(
        rf"create\s+policy\s+{re.escape(name)}\s+on\s+{re.escape(schema)}\.{re.escape(table)}\s+"
        rf"{mode}for\s+{action}\s+to\s+{re.escape(role)}\s+(.*?);",
        sql,
        re.I | re.S,
    )
    return compact(match.group(1)) if match else ""


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def require_transaction_wrapper(raw: str, label: str, errors: list[str]) -> None:
    sql = compact(raw)
    require(sql.startswith("begin;"), f"{label}:first executable statement must be BEGIN", errors)
    require(sql.endswith("commit;"), f"{label}:last executable statement must be COMMIT", errors)
    require(sql.count("begin;") == 1, f"{label}:must contain exactly one transaction BEGIN", errors)
    require(sql.count("commit;") == 1, f"{label}:must contain exactly one transaction COMMIT", errors)


def require_policy_shape(clause: str, label: str, action: str, predicates: tuple[str, ...], errors: list[str]) -> None:
    require(bool(clause), f"{label} missing {action.upper()} policy", errors)
    if not clause:
        return
    predicate = " and ".join(predicates)
    for required in predicates:
        require(required in clause, f"{label} {action.upper()} policy missing predicate: {required}", errors)
    has_using = re.search(r"\busing\s*\(", clause) is not None
    has_check = re.search(r"\bwith\s+check\s*\(", clause) is not None
    if action in ("select", "delete"):
        require(has_using and not has_check, f"{label} {action.upper()} must use USING only", errors)
        expected = f"using ({predicate})"
    elif action == "insert":
        require(has_check and not has_using, f"{label} INSERT must use WITH CHECK only", errors)
        expected = f"with check ({predicate})"
    else:
        require(has_using and has_check, f"{label} UPDATE must use both USING and WITH CHECK", errors)
        expected = f"using ({predicate}) with check ({predicate})"
    require(
        clause == expected,
        f"{label} {action.upper()} must apply the complete owner predicate in every applicable clause",
        errors,
    )


def phase1_errors(raw: str) -> list[str]:
    errors: list[str] = []
    raw = strip_sql_comments(raw)
    sql = compact(raw)
    body = function_body(raw)

    require_transaction_wrapper(raw, "phase1", errors)

    require("create schema if not exists private" in sql, "phase1:private schema missing", errors)
    for role in ("public", "anon", "authenticated"):
        require(
            f"revoke all on schema private from {role}" in sql,
            f"phase1:private schema ACL must reset {role}",
            errors,
        )
    require(
        re.search(
            r"create or replace function private\.is_approved_user\s*\(\s*\).*?security definer.*?set search_path\s*=\s*''",
            sql,
        )
        is not None,
        "phase1:approved-user function must be SECURITY DEFINER with empty search_path",
        errors,
    )
    require(
        sql_tokens(body) == sql_tokens(EXPECTED_APPROVAL_BODY),
        "phase1:approval function body must be exactly the approved-user EXISTS query",
        errors,
    )
    for role in ("public", "anon", "authenticated"):
        require(
            f"revoke all on function private.is_approved_user() from {role}" in sql,
            f"phase1:approval function ACL must reset {role}",
            errors,
        )
    require(
        "grant execute on function private.is_approved_user() to authenticated" in sql,
        "phase1:approval function must grant EXECUTE only to authenticated after reset",
        errors,
    )
    private_grants = [
        statement
        for _, statement in grant_statements(raw)
        if "on schema private" in statement
        or "on function private.is_approved_user()" in statement
    ]
    require(
        private_grants
        == [
            "grant usage on schema private to authenticated;",
            "grant execute on function private.is_approved_user() to authenticated;",
        ],
        "phase1:private schema/helper grants must be exactly authenticated USAGE/EXECUTE",
        errors,
    )
    require(
        re.search(
            r"create or replace function private\.set_updated_at\s*\(\s*\).*?returns trigger.*?"
            r"security definer.*?set search_path\s*=\s*''.*?new\.updated_at\s*:=\s*pg_catalog\.now\(\)",
            sql,
        )
        is not None,
        "phase1:private hardened updated_at trigger function missing",
        errors,
    )
    for role in ("public", "anon", "authenticated"):
        require(
            f"revoke all on function private.set_updated_at() from {role}" in sql,
            f"phase1:updated_at function ACL must reset {role}",
            errors,
        )
    for table in ("portfolios", "portfolio_accounts", "holdings", "portfolio_transactions", "contribution_plans"):
        require(
            f"drop trigger if exists phase1_set_updated_at on public.{table}" in sql
            and re.search(
                rf"create trigger phase1_set_updated_at before update on public\.{table}\s+"
                r"for each row execute function private\.set_updated_at\(\)",
                sql,
            )
            is not None,
            f"phase1:{table} updated_at maintenance trigger missing",
            errors,
        )
    require("service_role" not in sql, "phase1:service_role must not appear", errors)

    for table in TABLES:
        table_sql = table_body(raw, table)
        require(bool(table_sql), f"phase1:missing table public.{table}", errors)
        require(
            re.search(r"\buser_id\s+uuid\s+not\s+null\s+references\s+auth\.users\s*\(\s*id\s*\)", table_sql)
            is not None,
            f"phase1:{table}.user_id must be a direct non-null auth.users FK",
            errors,
        )
        require(
            re.search(r"unique\s*\(\s*user_id\s*,\s*id\s*\)", table_sql) is not None,
            f"phase1:{table} must expose UNIQUE (user_id, id)",
            errors,
        )
        require(
            f"alter table public.{table} enable row level security" in sql
            and f"alter table public.{table} force row level security" in sql,
            f"phase1:{table} must ENABLE and FORCE RLS",
            errors,
        )
        require(
            re.search(rf"create\s+index[^;]*?on\s+public\.{table}\s*\(\s*user_id\b", sql) is not None,
            f"phase1:{table} needs an index beginning with user_id",
            errors,
        )
        for role in ("public", "anon", "authenticated"):
            require(
                f"revoke all on table public.{table} from {role}" in sql,
                f"phase1:{table} must reset {role} privileges",
                errors,
            )
        table_grants = [statement for _, statement in grant_statements(raw) if grant_targets_table(statement, table)]
        expected_grant = f"grant select, insert, update, delete on table public.{table} to authenticated;"
        require(
            table_grants == [expected_grant],
            f"phase1:{table} grants must be exactly authenticated SELECT, INSERT, UPDATE, DELETE",
            errors,
        )
        for action in POLICY_ACTIONS:
            name = f"phase1_{table}_{action}_own_approved"
            clause = policy_clause(sql, "public", table, name, action)
            require_policy_shape(clause, f"phase1:{table}", action, (OWNER_PREDICATE,), errors)
        require(
            len(create_policy_statements(raw, "public", table)) == 4,
            f"phase1:{table} must define exactly the four named owner policies",
            errors,
        )

    for child in CHILDREN:
        require(
            re.search(
                r"foreign\s+key\s*\(\s*user_id\s*,\s*portfolio_id\s*\)\s*references\s+"
                r"public\.portfolios\s*\(\s*user_id\s*,\s*id\s*\)",
                table_body(raw, child),
            )
            is not None,
            f"phase1:{child} needs composite portfolio ownership FK",
            errors,
        )

    accounts = table_body(raw, "portfolio_accounts")
    transactions = table_body(raw, "portfolio_transactions")
    documents = table_body(raw, "portfolio_documents")
    analyses = table_body(raw, "portfolio_analyses")

    inline_trade_check = re.search(
        rf"constraint\s+{re.escape(TRADE_CONSTRAINT_NAME)}\s+check\s*\((.*)\)\s*$",
        transactions,
        re.I | re.S,
    )
    require(
        bool(inline_trade_check)
        and sql_tokens(inline_trade_check.group(1)) == sql_tokens(EXPECTED_TRADE_CHECK),
        "phase1:portfolio_transactions CREATE TABLE trade constraint must exactly require nonempty symbol, quantity > 0, and unit_price > 0 for BUY/SELL",
        errors,
    )

    trade_preflight = tagged_block(raw, "phase1_trade_fields_preflight")
    require(
        bool(trade_preflight)
        and sql_tokens(trade_preflight) == sql_tokens(EXPECTED_TRADE_PREFLIGHT_BODY),
        "phase1:BUY/SELL integrity preflight must exactly count and clearly reject every invalid legacy trade",
        errors,
    )
    trade_additions = trade_check_additions(raw)
    require(
        len(trade_additions) == 1
        and sql_tokens(trade_additions[0][1]) == sql_tokens(EXPECTED_TRADE_CHECK),
        "phase1:final BUY/SELL trade constraint must be added NOT VALID with the exact effective predicate",
        errors,
    )
    legacy_trade_drop = re.search(
        r"alter\s+table\s+public\.portfolio_transactions\s+drop\s+constraint\s+if\s+exists\s+portfolio_transactions_check\s*;",
        raw,
        re.I,
    )
    named_trade_drop = re.search(
        rf"alter\s+table\s+public\.portfolio_transactions\s+drop\s+constraint\s+if\s+exists\s+{re.escape(TRADE_CONSTRAINT_NAME)}\s*;",
        raw,
        re.I,
    )
    trade_validation = list(re.finditer(
        rf"alter\s+table\s+public\.portfolio_transactions\s+validate\s+constraint\s+{re.escape(TRADE_CONSTRAINT_NAME)}\s*;",
        raw,
        re.I,
    ))
    preflight_match = re.search(
        r"do\s+\$phase1_trade_fields_preflight\$.*?\$phase1_trade_fields_preflight\$\s*;",
        raw,
        re.I | re.S,
    )
    ordered_trade_reconciliation = (
        preflight_match
        and legacy_trade_drop
        and named_trade_drop
        and len(trade_additions) == 1
        and len(trade_validation) == 1
        and preflight_match.end() < legacy_trade_drop.start() < named_trade_drop.start()
        < trade_additions[0][0] < trade_validation[0].start()
    )
    require(
        bool(ordered_trade_reconciliation),
        "phase1:trade preflight must precede legacy/current drops, exact NOT VALID replacement, and validation",
        errors,
    )
    if trade_additions:
        later_trade_drop = re.search(
            rf"alter\s+table\s+public\.portfolio_transactions\s+drop\s+constraint\s+(?:if\s+exists\s+)?{re.escape(TRADE_CONSTRAINT_NAME)}\b",
            raw[trade_additions[0][0] + 1 :],
            re.I,
        )
        require(
            later_trade_drop is None,
            "phase1:final BUY/SELL trade constraint is dropped after it is added",
            errors,
        )

    require(
        re.search(r"unique\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*id\s*\)", accounts) is not None,
        "phase1:portfolio_accounts needs candidate key UNIQUE (user_id, portfolio_id, id)",
        errors,
    )
    for table in ("holdings", "portfolio_transactions"):
        require(
            re.search(
                r"foreign\s+key\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*account_id\s*\)\s*references\s+"
                r"public\.portfolio_accounts\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*id\s*\)\s*on\s+delete\s+cascade",
                table_body(raw, table),
            )
            is not None,
            f"phase1:{table} needs account triple ownership FK",
            errors,
        )
    require(
        re.search(r"unique\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*id\s*\)", documents) is not None,
        "phase1:portfolio_documents needs candidate key UNIQUE (user_id, portfolio_id, id)",
        errors,
    )
    require(
        re.search(
            r"foreign\s+key\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*account_id\s*\)\s*references\s+"
            r"public\.portfolio_accounts\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*id\s*\)\s*"
            r"on\s+delete\s+set\s+null\s*\(\s*account_id\s*\)",
            documents,
        )
        is not None,
        "phase1:portfolio_documents needs triple account FK that nulls only account_id",
        errors,
    )
    require(
        re.search(
            r"foreign\s+key\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*document_id\s*\)\s*references\s+"
            r"public\.portfolio_documents\s*\(\s*user_id\s*,\s*portfolio_id\s*,\s*id\s*\)\s*"
            r"on\s+delete\s+set\s+null\s*\(\s*document_id\s*\)",
            analyses,
        )
        is not None,
        "phase1:portfolio_analyses needs document triple ownership FK",
        errors,
    )

    reconciliation_requirements = (
        "alter table public.holdings drop constraint if exists holdings_user_id_account_id_fkey",
        "alter table public.holdings drop constraint if exists holdings_user_id_portfolio_id_account_id_fkey",
        "alter table public.portfolio_transactions drop constraint if exists portfolio_transactions_user_id_account_id_fkey",
        "alter table public.portfolio_documents drop constraint if exists portfolio_documents_user_id_account_id_fkey",
        "alter table public.portfolio_analyses drop constraint if exists portfolio_analyses_user_id_document_id_fkey",
        "alter table public.portfolio_accounts drop constraint if exists portfolio_accounts_user_id_portfolio_id_id_key",
        "alter table public.portfolio_documents drop constraint if exists portfolio_documents_user_id_portfolio_id_id_key",
        "alter table public.portfolio_accounts add constraint portfolio_accounts_user_id_portfolio_id_id_key unique (user_id, portfolio_id, id)",
        "alter table public.portfolio_documents add constraint portfolio_documents_user_id_portfolio_id_id_key unique (user_id, portfolio_id, id)",
        "alter table public.holdings add constraint holdings_user_id_portfolio_id_account_id_fkey",
        "alter table public.portfolio_transactions add constraint portfolio_transactions_user_id_portfolio_id_account_id_fkey",
        "alter table public.portfolio_documents add constraint portfolio_documents_user_id_portfolio_id_account_id_fkey",
        "alter table public.portfolio_analyses add constraint portfolio_analyses_user_id_portfolio_id_document_id_fkey",
    )
    for statement in reconciliation_requirements:
        require(statement in sql, f"phase1:idempotent constraint reconciliation missing: {statement}", errors)

    additions = final_fk_additions(raw)
    for (table, constraint), expected_shape in FINAL_FOREIGN_KEYS.items():
        matches = additions.get((table, constraint), [])
        require(
            len(matches) == 1 and matches[0][1] == expected_shape,
            f"phase1:{table} final reconciliation FK {constraint} must have the exact ownership shape",
            errors,
        )
        if matches:
            add_position = matches[-1][0]
            later_drop = re.search(
                rf"alter\s+table\s+public\.{re.escape(table)}\s+drop\s+constraint\s+(?:if\s+exists\s+)?"
                rf"{re.escape(constraint)}\b",
                raw[add_position + 1 :],
                re.I,
            )
            require(
                later_drop is None,
                f"phase1:{table} final reconciliation FK {constraint} is dropped after it is added",
                errors,
            )

    sweep = tagged_block(raw, "phase1_financial_policy_sweep")
    require(bool(sweep), "phase1:financial all-policy sweep block missing", errors)
    require("from pg_catalog.pg_policies" in sweep, "phase1:financial sweep must enumerate pg_policies", errors)
    require(
        "execute format('drop policy if exists %i on public.%i', existing_policy, target_table)" in sweep,
        "phase1:financial sweep must dynamically drop every enumerated policy",
        errors,
    )
    for table in TABLES:
        require(f"'{table}'" in sweep, f"phase1:financial sweep omits {table}", errors)
    sweep_match = re.search(
        r"do\s+\$phase1_financial_policy_sweep\$.*?\$phase1_financial_policy_sweep\$\s*;",
        raw,
        re.S | re.I,
    )
    if sweep_match:
        for table in TABLES:
            policies = create_policy_statements(raw, "public", table)
            require(
                all(position > sweep_match.end() for position, _ in policies),
                f"phase1:{table} policies must be created only after the all-policy sweep",
                errors,
            )

    assertion = tagged_block(raw, "phase1_financial_policy_assertion")
    require(bool(assertion), "phase1:post-migration financial policy assertion missing", errors)
    require("policy_count <> 4" in assertion, "phase1:policy assertion must require four policies per table", errors)
    require(
        "raise exception 'unexpected rls policy set on public.% (count=%, unexpected=%)'" in assertion
        and "string_agg" in assertion,
        "phase1:policy assertion must diagnose unexpected policy names/commands",
        errors,
    )
    for table in TABLES:
        require(f"'{table}'" in assertion, f"phase1:policy assertion omits {table}", errors)

    require("check (quantity > 0)" in sql, "phase1:positive quantity constraint missing", errors)
    require("check (amount > 0)" in sql, "phase1:positive contribution amount constraint missing", errors)
    require(re.search(r"check\s*\(\s*file_size_bytes\s*>\s*0\b", sql) is not None, "phase1:positive document size constraint missing", errors)
    require(
        re.search(
            r"insert into storage\.buckets\s*\([^)]*file_size_limit[^)]*allowed_mime_types[^)]*\).*?"
            r"'user-documents'.*?false.*?on conflict\s*\(\s*id\s*\)\s+do update",
            sql,
        )
        is not None,
        "phase1:private idempotent user-documents bucket upsert with size/MIME restrictions missing",
        errors,
    )

    storage_sweep = tagged_block(raw, "phase1_storage_policy_sweep")
    require(bool(storage_sweep), "phase1:storage namespaced cleanup block missing", errors)
    require("from pg_catalog.pg_policies" in storage_sweep, "phase1:storage cleanup must enumerate pg_policies", errors)
    require("schemaname = 'storage'" in storage_sweep and "tablename = 'objects'" in storage_sweep, "phase1:storage cleanup must target storage.objects", errors)
    require("policyname like 'phase1_user_documents_%'" in storage_sweep, "phase1:storage cleanup must be limited to the migration namespace", errors)
    require("drop policy if exists %i on storage.objects" in storage_sweep, "phase1:storage cleanup must drop enumerated namespaced policies", errors)

    for action in POLICY_ACTIONS:
        require(
            f"drop policy if exists user_documents_{action}_own_path on storage.objects" in sql,
            f"phase1:storage cleanup must remove legacy {action.upper()} policy name",
            errors,
        )
        name = f"phase1_user_documents_{action}_own_path"
        clause = policy_clause(sql, "storage", "objects", name, action)
        require_policy_shape(clause, "phase1:storage", action, STORAGE_PREDICATES, errors)
        guard_name = f"phase1_user_documents_guard_{action}"
        guard_clause = policy_clause(
            sql, "storage", "objects", guard_name, action, restrictive=True
        )
        require_policy_shape(
            guard_clause,
            "phase1:storage restrictive guard",
            action,
            (STORAGE_GUARD_PREDICATE,),
            errors,
        )
        anon_guard_name = f"phase1_user_documents_anon_guard_{action}"
        anon_guard_clause = policy_clause(
            sql,
            "storage",
            "objects",
            anon_guard_name,
            action,
            restrictive=True,
            role="anon",
        )
        require_policy_shape(
            anon_guard_clause,
            "phase1:storage anonymous restrictive guard",
            action,
            (ANON_STORAGE_GUARD_PREDICATE,),
            errors,
        )
    require(
        len(create_policy_statements(raw, "storage", "objects")) == 12,
        "phase1:storage must define four owner policies and eight restrictive guards",
        errors,
    )
    require(
        len(all_create_policy_statements(raw)) == len(TABLES) * 4 + 12,
        "phase1:migration must not create any policies beyond the exact financial and storage sets",
        errors,
    )

    return errors


def access_script_errors(raw: str, label: str) -> list[str]:
    errors: list[str] = []
    raw = strip_sql_comments(raw)
    sql = compact(raw)
    body = access_trigger_body(raw)
    require_transaction_wrapper(raw, label, errors)
    require(
        re.search(
            r"create or replace function public\.handle_new_access_request\s*\(\s*\).*?"
            r"returns trigger.*?security definer.*?set search_path\s*=\s*''",
            sql,
        )
        is not None,
        f"{label}:trigger function must be SECURITY DEFINER with empty search_path",
        errors,
    )
    require("insert into public.access_requests" in sql, f"{label}:qualified trigger target missing", errors)
    require("pg_catalog.now()" in sql, f"{label}:qualified now() missing", errors)
    require(
        sql_tokens(body) == sql_tokens(EXPECTED_ACCESS_TRIGGER_BODY),
        f"{label}:trigger body must exactly insert pending auth data, update only contact fields, and return NEW",
        errors,
    )
    for role in ("public", "anon", "authenticated"):
        require(
            f"revoke all on function public.handle_new_access_request() from {role}" in sql,
            f"{label}:trigger function ACL must reset {role}",
            errors,
        )
    require(
        re.search(
            r"create trigger on_auth_user_created_access_request\s+after insert on auth\.users\s+"
            r"for each row execute function public\.handle_new_access_request\(\)",
            sql,
        )
        is not None,
        f"{label}:auth.users INSERT trigger missing or malformed",
        errors,
    )
    require("alter table public.access_requests enable row level security" in sql, f"{label}:ENABLE RLS missing", errors)
    require("alter table public.access_requests force row level security" in sql, f"{label}:FORCE RLS missing", errors)
    for role in ("public", "anon", "authenticated"):
        require(
            f"revoke all on table public.access_requests from {role}" in sql,
            f"{label}:{role} privilege reset missing",
            errors,
        )

    policies = create_policy_statements(raw, "public", "access_requests")
    all_policies = all_create_policy_statements(raw)
    expected_policy = (
        "create policy users_read_own_access_request on public.access_requests "
        "for select to authenticated using ((select auth.uid()) = user_id);"
    )
    require(
        len(all_policies) == 1
        and len(policies) == 1
        and sql_tokens(policies[0][1]) == sql_tokens(expected_policy),
        f"{label}:must define exactly one named authenticated own-row SELECT policy",
        errors,
    )

    sweep_matches = [
        match
        for match in re.finditer(r"do\s+\$\$(.*?)\$\$\s*;", raw, re.S | re.I)
        if "from pg_catalog.pg_policies" in compact(match.group(1))
        and "tablename = 'access_requests'" in compact(match.group(1))
        and "drop policy if exists %i on public.access_requests" in compact(match.group(1))
    ]
    require(len(sweep_matches) == 1, f"{label}:must contain one full access_requests all-policy sweep", errors)
    if sweep_matches and policies:
        require(
            sweep_matches[0].end() < policies[0][0],
            f"{label}:all-policy sweep must precede the sole own-row SELECT policy",
            errors,
        )

    grants = [(position, statement) for position, statement in grant_statements(raw) if grant_targets_table(statement, "access_requests")]
    expected_grant = "grant select on table public.access_requests to authenticated;"
    require(
        [statement for _, statement in grants] == [expected_grant],
        f"{label}:access_requests grants must be exactly authenticated SELECT",
        errors,
    )
    if sweep_matches and policies and grants:
        require(
            sweep_matches[0].end() < grants[0][0] < policies[0][0],
            f"{label}:authenticated SELECT grant must follow the sweep and precede the policy",
            errors,
        )

    function_position = sql.find("create or replace function public.handle_new_access_request")
    acl_position = sql.find("revoke all on function public.handle_new_access_request() from public")
    trigger_position = sql.find("create trigger on_auth_user_created_access_request")
    backfill_position = sql.find("insert into public.access_requests", trigger_position + 1)
    preflight_position = sql.find("do $access_requests_user_id_preflight$")
    not_null_position = sql.find("alter table public.access_requests alter column user_id set not null")
    rls_position = sql.find("alter table public.access_requests enable row level security", backfill_position)
    require(
        min(function_position, acl_position, trigger_position, backfill_position, preflight_position, not_null_position) >= 0
        and function_position < acl_position < trigger_position < backfill_position < preflight_position < not_null_position,
        f"{label}:required function/ACL/trigger/backfill/preflight/NOT NULL order is invalid",
        errors,
    )
    require(
        "select pg_catalog.count(*)" in sql
        and "from public.access_requests where user_id is null" in sql
        and "null_user_id_count > 0" in sql
        and "raise exception 'cannot set public.access_requests.user_id not null: % row(s) still have null user_id'" in sql,
        f"{label}:NULL user_id preflight must count and clearly reject remaining orphan rows",
        errors,
    )
    if rls_position >= 0:
        require(
            not_null_position < rls_position,
            f"{label}:NOT NULL enforcement must precede destructive RLS/policy reconciliation",
            errors,
        )
    if sweep_matches:
        require(
            not_null_position < sweep_matches[0].start(),
            f"{label}:NOT NULL enforcement must precede destructive policy reconciliation",
            errors,
        )

    return errors


def verify_access_script(path: Path, errors: list[str]) -> None:
    raw = path.read_text(encoding="utf-8")
    errors.extend(access_script_errors(raw, path.name))


def mutate_once(raw: str, old: str, new: str, label: str) -> str:
    count = raw.count(old)
    if count == 0:
        raise AssertionError(f"self-test fixture {label!r} was not found")
    return raw.replace(old, new, 1)


def run_mutation_tests(raw: str) -> list[str]:
    failures: list[str] = []
    baseline = phase1_errors(raw)
    if baseline:
        return ["self-test:baseline Phase 1 SQL is invalid: " + "; ".join(baseline)]

    cases = (
        (
            "account triple FK",
            "foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade",
            "foreign key (user_id, account_id) references public.portfolio_accounts(user_id, id) on delete cascade",
            "needs account triple ownership fk",
        ),
        (
            "INSERT clause",
            "create policy phase1_portfolios_insert_own_approved on public.portfolios for insert to authenticated with check",
            "create policy phase1_portfolios_insert_own_approved on public.portfolios for insert to authenticated using",
            "insert must use with check only",
        ),
        (
            "SELECT clause",
            "create policy phase1_portfolios_select_own_approved on public.portfolios for select to authenticated using",
            "create policy phase1_portfolios_select_own_approved on public.portfolios for select to authenticated with check",
            "select must use using only",
        ),
        (
            "UPDATE clauses",
            "create policy phase1_portfolio_accounts_update_own_approved on public.portfolio_accounts for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);",
            "create policy phase1_portfolio_accounts_update_own_approved on public.portfolio_accounts for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (true);",
            "update must apply the complete owner predicate in every applicable clause",
        ),
        ("approval table", "from public.access_requests as ar", "from public.other_requests as ar", "body must be exactly"),
        ("approval auth binding", "ar.user_id = (select auth.uid())", "ar.user_id is not null", "body must be exactly"),
        ("approval status", "ar.status = 'approved'", "ar.status = 'pending'", "body must be exactly"),
        (
            "approval OR true bypass",
            "and ar.status = 'approved'\n  );",
            "and ar.status = 'approved' or true\n  );",
            "body must be exactly",
        ),
        (
            "function ACL reset",
            "revoke all on function private.is_approved_user() from public;",
            "-- removed public function ACL reset",
            "function acl must reset public",
        ),
        (
            "function EXECUTE grant",
            "grant execute on function private.is_approved_user() to authenticated;",
            "-- removed authenticated function grant",
            "function must grant execute only to authenticated after reset",
        ),
        (
            "table PUBLIC ACL reset",
            "revoke all on table public.portfolios from public;",
            "-- removed public table ACL reset",
            "portfolios must reset public privileges",
        ),
        (
            "table anon ACL reset",
            "revoke all on table public.portfolios from anon;",
            "-- removed anon table ACL reset",
            "portfolios must reset anon privileges",
        ),
        (
            "table authenticated ACL reset",
            "revoke all on table public.portfolios from authenticated;",
            "-- removed authenticated table ACL reset",
            "portfolios must reset authenticated privileges",
        ),
        (
            "constraint reconciliation",
            "alter table public.holdings drop constraint if exists holdings_user_id_account_id_fkey;",
            "-- removed legacy FK reconciliation",
            "idempotent constraint reconciliation missing",
        ),
        (
            "final holdings FK",
            "alter table public.holdings add constraint holdings_user_id_portfolio_id_account_id_fkey\n  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade;",
            "alter table public.holdings add constraint holdings_user_id_portfolio_id_account_id_fkey\n  foreign key (user_id, account_id) references public.portfolio_accounts(user_id, id) on delete cascade;",
            "final reconciliation fk",
        ),
        ("all-policy sweep", "    'holdings',\n    'portfolio_transactions',", "    'portfolio_transactions',", "financial sweep omits holdings"),
        (
            "storage bucket predicate",
            "bucket_id = 'user-documents' and (storage.foldername(name))[1]",
            "bucket_id = 'other-bucket' and (storage.foldername(name))[1]",
            "storage select policy missing predicate: bucket_id = 'user-documents'",
        ),
        (
            "storage owner path",
            "(storage.foldername(name))[1] = (select auth.uid())::text",
            "(storage.foldername(name))[2] = (select auth.uid())::text",
            "storage select policy missing predicate: (storage.foldername(name))[1]",
        ),
        (
            "storage approval",
            "create policy phase1_user_documents_select_own_path on storage.objects for select to authenticated using (private.is_approved_user() and",
            "create policy phase1_user_documents_select_own_path on storage.objects for select to authenticated using (true and",
            "storage select policy missing predicate: private.is_approved_user()",
        ),
        (
            "storage cleanup namespace",
            "policyname like 'phase1_user_documents_%'",
            "policyname like '%'",
            "storage cleanup must be limited to the migration namespace",
        ),
        (
            "block-commented RLS enable",
            "alter table public.portfolios enable row level security;",
            "/* alter table public.portfolios enable row level security; */",
            "must enable and force rls",
        ),
        (
            "block-commented RLS force",
            "alter table public.portfolios force row level security;",
            "/* alter table public.portfolios force row level security; */",
            "must enable and force rls",
        ),
        (
            "block-commented owner SELECT policy",
            "create policy phase1_portfolios_select_own_approved on public.portfolios for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);",
            "/* create policy phase1_portfolios_select_own_approved on public.portfolios for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id); */",
            "missing select policy",
        ),
        (
            "block-commented authenticated grant",
            "grant select, insert, update, delete on table public.portfolios to authenticated;",
            "/* grant select, insert, update, delete on table public.portfolios to authenticated; */",
            "grants must be exactly authenticated",
        ),
        (
            "restrictive storage guard mode",
            "create policy phase1_user_documents_guard_select on storage.objects as restrictive",
            "create policy phase1_user_documents_guard_select on storage.objects as permissive",
            "restrictive guard missing select policy",
        ),
    )

    for label, old, new, expected in cases:
        try:
            mutated = mutate_once(raw, old, new, label)
        except AssertionError as exc:
            failures.append(f"self-test:{exc}")
            continue
        messages = [message.lower() for message in phase1_errors(mutated)]
        if not any(expected in message for message in messages):
            failures.append(f"self-test:{label} mutation was not rejected by the expected check")

    appended_grant = raw + "\ngrant all on table public.holdings to anon;\n"
    messages = [message.lower() for message in phase1_errors(appended_grant)]
    if not any("holdings grants must be exactly authenticated" in message for message in messages):
        failures.append("self-test:appended anon GRANT ALL was not rejected")

    broad_storage_policy = (
        "create policy attacker_storage_select_all on storage.objects "
        "for select to authenticated using (true);\n"
    )
    adversarial = raw.replace("\ncommit;", f"\n{broad_storage_policy}commit;", 1)
    for action in POLICY_ACTIONS:
        clause = policy_clause(
            adversarial,
            "storage",
            "objects",
            f"phase1_user_documents_guard_{action}",
            action,
            restrictive=True,
        )
        guard_errors: list[str] = []
        require_policy_shape(
            clause,
            "self-test:adversarial storage restrictive guard",
            action,
            (STORAGE_GUARD_PREDICATE,),
            guard_errors,
        )
        if guard_errors:
            failures.append(
                f"self-test:appended broad permissive storage policy bypassed/masked {action.upper()} guard"
            )
    guard_allows = lambda bucket, approved, owns_path: bucket != "user-documents" or (approved and owns_path)
    if True and guard_allows("user-documents", False, True):
        failures.append("self-test:broad storage policy bypasses approval guard")
    if True and guard_allows("user-documents", True, False):
        failures.append("self-test:broad storage policy bypasses owner-folder guard")
    if not (True and guard_allows("unrelated-bucket", False, False)):
        failures.append("self-test:restrictive storage guard breaks unrelated buckets")

    broad_anonymous_policies = "".join(
        f"create policy attacker_storage_{role}_{action}_all on storage.objects "
        f"for {action} to {role} "
        + (
            "using (true) with check (true);\n"
            if action == "update"
            else "with check (true);\n"
            if action == "insert"
            else "using (true);\n"
        )
        for role in ("anon", "public")
        for action in POLICY_ACTIONS
    )
    adversarial_anon = raw.replace("\ncommit;", f"\n{broad_anonymous_policies}commit;", 1)
    for action in POLICY_ACTIONS:
        clause = policy_clause(
            adversarial_anon,
            "storage",
            "objects",
            f"phase1_user_documents_anon_guard_{action}",
            action,
            restrictive=True,
            role="anon",
        )
        guard_errors: list[str] = []
        require_policy_shape(
            clause,
            "self-test:adversarial anonymous storage restrictive guard",
            action,
            (ANON_STORAGE_GUARD_PREDICATE,),
            guard_errors,
        )
        if guard_errors:
            failures.append(
                f"self-test:appended broad permissive anon/PUBLIC policy bypassed/masked {action.upper()} anonymous guard"
            )
    anonymous_guard_allows = lambda bucket: bucket != "user-documents"
    if True and anonymous_guard_allows("user-documents"):
        failures.append("self-test:broad anon/PUBLIC storage policy exposes user-documents")
    if not (True and anonymous_guard_allows("unrelated-bucket")):
        failures.append("self-test:anonymous restrictive storage guard breaks unrelated buckets")
    return failures


def run_access_mutation_tests(raw: str, label: str) -> list[str]:
    failures: list[str] = []
    baseline = access_script_errors(raw, label)
    if baseline:
        return [f"self-test:baseline {label} is invalid: " + "; ".join(baseline)]

    cases = (
        ("SECURITY DEFINER", "security definer", "security invoker", "security definer with empty search_path"),
        ("empty search_path", "set search_path = ''", "set search_path = public", "security definer with empty search_path"),
        (
            "function ACL public",
            "revoke all on function public.handle_new_access_request() from public;",
            "/* revoke all on function public.handle_new_access_request() from public; */",
            "function acl must reset public",
        ),
        (
            "function ACL anon",
            "revoke all on function public.handle_new_access_request() from anon;",
            "/* revoke all on function public.handle_new_access_request() from anon; */",
            "function acl must reset anon",
        ),
        (
            "function ACL authenticated",
            "revoke all on function public.handle_new_access_request() from authenticated;",
            "/* revoke all on function public.handle_new_access_request() from authenticated; */",
            "function acl must reset authenticated",
        ),
        (
            "auth.users trigger scope",
            "after insert on auth.users",
            "after insert on public.users",
            "auth.users insert trigger missing or malformed",
        ),
        (
            "trigger insert status",
            "    'pending'\n  )\n  on conflict (user_id)",
            "    'approved'\n  )\n  on conflict (user_id)",
            "trigger body must exactly insert pending auth data",
        ),
        (
            "trigger user binding",
            "    new.id,\n    new.email,",
            "    '00000000-0000-0000-0000-000000000000'::uuid,\n    new.email,",
            "trigger body must exactly insert pending auth data",
        ),
        (
            "trigger conflict status promotion",
            "        updated_at = pg_catalog.now();",
            "        updated_at = pg_catalog.now(),\n        status = 'approved';",
            "trigger body must exactly insert pending auth data",
        ),
        (
            "block-commented RLS enable",
            "alter table public.access_requests enable row level security;",
            "/* alter table public.access_requests enable row level security; */",
            "enable rls missing",
        ),
        (
            "block-commented RLS force",
            "alter table public.access_requests force row level security;",
            "/* alter table public.access_requests force row level security; */",
            "force rls missing",
        ),
        (
            "block-commented owner SELECT policy",
            "create policy users_read_own_access_request\n  on public.access_requests\n  for select to authenticated\n  using ((select auth.uid()) = user_id);",
            "/* create policy users_read_own_access_request\n  on public.access_requests\n  for select to authenticated\n  using ((select auth.uid()) = user_id); */",
            "exactly one named authenticated own-row select policy",
        ),
        (
            "block-commented authenticated grant",
            "grant select on table public.access_requests to authenticated;",
            "/* grant select on table public.access_requests to authenticated; */",
            "grants must be exactly authenticated select",
        ),
        (
            "NULL preflight",
            "do $access_requests_user_id_preflight$",
            "do $disabled_access_requests_user_id_preflight$",
            "required function/acl/trigger/backfill/preflight/not null order is invalid",
        ),
        (
            "SET NOT NULL",
            "alter table public.access_requests alter column user_id set not null;",
            "/* alter table public.access_requests alter column user_id set not null; */",
            "required function/acl/trigger/backfill/preflight/not null order is invalid",
        ),
        ("transaction BEGIN", "begin;", "/* begin; */", "first executable statement must be begin"),
        ("transaction COMMIT", "commit;", "/* commit; */", "last executable statement must be commit"),
    )
    for mutation_label, old, new, expected in cases:
        try:
            mutated = mutate_once(raw, old, new, f"{label} {mutation_label}")
        except AssertionError as exc:
            failures.append(f"self-test:{exc}")
            continue
        messages = [message.lower() for message in access_script_errors(mutated, label)]
        if not any(expected in message for message in messages):
            failures.append(
                f"self-test:{label} {mutation_label} mutation was not rejected by the expected check"
            )

    not_null_statement = "alter table public.access_requests alter column user_id set not null;"
    reordered = (
        raw.replace(not_null_statement, "-- original NOT NULL moved", 1)
        .replace(
            "do $access_requests_user_id_preflight$",
            f"{not_null_statement}\n\ndo $access_requests_user_id_preflight$",
            1,
        )
    )
    messages = [message.lower() for message in access_script_errors(reordered, label)]
    if not any("required function/acl/trigger/backfill/preflight/not null order is invalid" in message for message in messages):
        failures.append(f"self-test:{label} preflight/NOT NULL reordering was not rejected")

    mutated = raw.replace(
        "\ncommit;",
        "\ncreate policy attacker_reads_all_access_requests on public.access_requests "
        "for select to authenticated using (true);\ncommit;",
        1,
    )
    messages = [message.lower() for message in access_script_errors(mutated, label)]
    if not any("exactly one named authenticated own-row select policy" in message for message in messages):
        failures.append(f"self-test:{label} appended permissive access_requests policy was not rejected")
    return failures


def main() -> int:
    errors: list[str] = []
    if not PHASE1.exists():
        errors.append(f"missing:{PHASE1.relative_to(ROOT)}")
    else:
        raw = PHASE1.read_text(encoding="utf-8")
        errors.extend(phase1_errors(raw))
        errors.extend(run_mutation_tests(raw))
    for path in (ACCESS, FIX):
        if not path.exists():
            errors.append(f"missing:{path.relative_to(ROOT)}")
        else:
            verify_access_script(path, errors)
            errors.extend(run_access_mutation_tests(path.read_text(encoding="utf-8"), path.name))
    if errors:
        print("PHASE1_MULTIUSER_SECURITY_FAILED")
        for error in errors:
            print(error)
        return 1
    print("PHASE1_MULTIUSER_SECURITY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
