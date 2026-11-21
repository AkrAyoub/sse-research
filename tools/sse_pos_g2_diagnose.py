#!/usr/bin/env python3
"""R37: actual G2 Docker failure triage, bounded and WITHOUT raw container logs.

Never prints Docker stdout/stderr, container arguments, mounts, JWT, EIP-2335
keystore data or validator secret information. Classifications only. Read-only.
Only exact known chain31340 container names, not arbitrary operator inputs.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CONTAINERS = ("sse31340-g2-el", "sse31340-g2-bn", "sse31340-g2-vc")
MAX_LOG_BYTES = 300_000
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")

# Ordered, fixed string classifiers. Never emit a raw log line or dynamic
# group capture: even error messages can accidentally include secrets.
CATEGORIES = (
    ("CLI_ARGUMENT_OR_USAGE_ERROR", re.compile(
        r"unknown (?:argument|option)|unexpected argument|unrecognized option|"
        r"found argument|invalid (?:option|argument|command)|usage:", re.I)),
    ("CONFIG_OR_FORK_REJECTED", re.compile(
        r"(?:config|fork|preset|yaml|network).{0,100}(?:invalid|error|failed|"
        r"unsupported|mismatch|unable|unrecognized)|"
        r"(?:invalid|unsupported|mismatch|failed).{0,100}(?:fork|preset|config)", re.I)),
    ("GENESIS_SSZ_OR_STATE_REJECTED", re.compile(
        r"(?:genesis|ssz|beacon state|anchor).{0,120}(?:invalid|error|"
        r"failed|mismatch|decode|deserialize|unsupported|not valid|load)|"
        r"(?:invalid|failed|mismatch|unable).{0,120}(?:genesis|ssz|beacon state)", re.I)),
    ("READ_ONLY_OR_PERMISSION_FAILURE", re.compile(
        r"permission denied|read-only file system|operation not permitted|"
        r"access denied|eacces|erofs", re.I)),
    ("MISSING_INPUT_OR_FILE_PATH", re.compile(
        r"no such file|does not exist|not a file|could not open|"
        r"failed to open|file not found|unable to read|not found", re.I)),
    ("ENGINE_JWT_OR_AUTH_FAILURE", re.compile(
        r"(?:jwt|auth|secret).{0,100}(?:error|invalid|failed|denied|"
        r"unreadable|missing|malformed|reject)", re.I)),
    ("EXECUTION_ENDPOINT_UNAVAILABLE", re.compile(
        r"(?:execution|engine|endpoint|connection).{0,100}(?:refused|"
        r"unavailable|timeout|failed|unable|disconnected|error)", re.I)),
    ("PORT_BIND_FAILURE", re.compile(
        r"address already in use|port.*in use|failed to bind|"
        r"cannot bind|could not bind|listen.*fail", re.I)),
    ("RESOURCE_OR_OOM_FAILURE", re.compile(
        r"out of memory|out-of-memory|oom-kill|resource temporarily|"
        r"cannot allocate memory|memory allocation failed", re.I)),
    ("CRYPTOGRAPHIC_OR_VALIDATOR_ERROR", re.compile(
        r"(?:bls|validator|signature|keystore|slashing).{0,120}(?:"
        r"invalid|failed|unable|mismatch|error|refused)", re.I)),
    ("CLIENT_FATAL_OR_STARTUP_FAILURE", re.compile(
        r"failed to start|startup failed|could not start|"
        r"shutting down|fatal|panic|thread.*panicked|crit", re.I)),
)

# Safe, deliberately fixed dictionaries for deeper diagnoses. Only the label
# below is returned, NEVER text from a container's raw, potentially secret logs.
ROOT_CAUSE_HINTS = (
    ("GENESIS_JSON_LOADING", re.compile(r"genesis.{0,160}(?:json|parse|read|load|invalid|not valid|unsupported|error|fail)|(?:invalid|unable|parse|failed|read).{0,160}genesis", re.I)),
    ("GENESIS_ALLOC_ACCOUNT_FORMAT", re.compile(r"(?:alloc|predeploy|genesis account|balance|storage root|nonce|code hash).{0,140}(?:invalid|parse|error|fail|unsupported)", re.I)),
    ("EXECUTION_FORK_SCHEDULE", re.compile(r"(?:prague|cancun|shanghai|osaka|fulu|blob|paris|terminal.total.difficulty|fork schedule)", re.I)),
    ("EXECUTION_GENESIS_FIELDS", re.compile(r"(?:chain.?id|base.?fee|gas.?limit|header|difficulty|timestamp|mix.?hash|parent.?hash)", re.I)),
    ("JAVA_EXCEPTION_CLASS", re.compile(r"(?:\bException\b|\bError\b|Exception:|java\.lang\.)", re.I)),
    ("JAVA_ERROR_BAD_ARGUMENT", re.compile(r"(?:IllegalArgumentException|IllegalStateException|ParameterException|PicocliException|missing required option)", re.I)),
    ("JAVA_ERROR_OUT_OF_MEMORY", re.compile(r"(?:OutOfMemoryError|memory allocation|cannot allocate|oom)", re.I)),
    ("JAVA_ERROR_FILE_IO", re.compile(r"(?:NoSuchFileException|FileNotFoundException|AccessDeniedException|IOException|ReadOnlyFileSystemException)", re.I)),
    ("JAVA_ERROR_NETWORK", re.compile(r"(?:UnknownHostException|ConnectException|BindException|NoRouteToHostException)", re.I)),
    ("JAVA_ERROR_DATABASE", re.compile(r"(?:RocksDBException|rocksdb|database.{0,80}(?:open|error|fail|corrupt))", re.I)),
    ("ENGINE_AUTH_OR_JWT", re.compile(r"(?:jwt|engine[- ]?rpc|authentication|authorized|token)", re.I)),
    ("LIGHTHOUSE_TESTNET_DEPLOY_BLOCK", re.compile(r"deposit_contract_block\.txt|DEPLOY_BLOCK_FILE|Unable to open deploy_block|Unable to open deposit_contract_block", re.I)),
    ("LIGHTHOUSE_PRIVATE_VALIDATOR_DEF", re.compile(r"validator_definitions\.yml|voting-keystore\.json|secrets.dir|slashing_protection", re.I)),
    ("DOCKER_R35_READONLY_ROOT", re.compile(r"(?:read.only.file.system|Permission denied|AccessDeniedException|erofs)", re.I)),
    ("RPC_HOST_OR_LISTEN", re.compile(r"(?:host.?allowlist|hostname|socket|listen|address already in use)", re.I)),
)

def safe_root_hints(log_output: str) -> dict:
    """Allowlisted, static lexical indicators only: never reproduce log data."""
    counts = collections.Counter()
    # Security: evaluate only candidate error lines, not incidental success messages.
    for line in log_output.splitlines():
        if not ERROR_WORDS.search(line) and not re.search(r"Caused by|Exception|Traceback", line, re.I):
            continue
        for name, expr in ROOT_CAUSE_HINTS:
            if expr.search(line):
                counts[name] += 1
    return {name: counts[name] for name, _ in ROOT_CAUSE_HINTS if counts[name]}

ERROR_WORDS = re.compile(
    r"fatal|critical|crit|panic|failed|error|unable|could not|"
    r"invalid|unsupported|refused|unrecognized|unknown", re.I)


# R39: narrow symbolic introspection. ALL emitted values must be authored in
# source, never interpolated from raw JVM log lines. A huge secret-bearing
# error line cannot leak through a dynamic class-name or message printout.
JAVA_EXCEPTION_SIGNATURES = (
    "RuntimeException", "UnsupportedOperationException", "NullPointerException",
    "ClassCastException", "ExceptionInInitializerError", "SecurityException",
    "FileNotFoundException", "IOException", "UncheckedIOException",
    "FileSystemException", "AccessDeniedException", "NoSuchFileException",
    "ReadOnlyFileSystemException", "OutOfMemoryError",
    "IllegalStateException", "IllegalArgumentException",
    "UnmatchedArgumentException", "ParameterException", "ExecutionException",
    "JsonProcessingException", "JsonParseException", "JsonMappingException",
    "MismatchedInputException", "InvalidFormatException",
    "InvalidDefinitionException", "UnrecognizedPropertyException",
    "GenesisConfigFileException", "GenesisConfigurationException",
    "InvalidGenesisFileException", "InvalidConfigurationException",
    "StorageException", "RocksDBException",
    "NoClassDefFoundError", "ClassNotFoundException", "LinkageError",
    "UnknownHostException", "BindException", "ConnectException",
    "ConnectTimeoutException", "SocketException", "SSLException",
    "DecodeException", "ParseException", "ValidationException",
    "RejectedExecutionException", "TimeoutException",
    "UncheckedExecutionException", "Error", "Exception",
)
BESU_DIAGNOSTIC_SIGNATURES = (
    ("GENESIS_FIELD_NOT_RECOGNIZED", r"unrecognized field|unknown (?:property|field)|unknown key"),
    ("GENESIS_PARSE_OR_VALIDATION", r"parse genesis|read genesis|invalid genesis|genesis.{0,60}(?:parse|invalid|error|failure)|can't parse genesis"),
    ("GENESIS_FIELD_MISSING", r"missing (?:required )?(?:field|attribute|key)|required field"),
    ("GENESIS_FIELD_NUMBER_ERROR", r"numberformatexception|number format|numeric value|out of range|value is too large"),
    ("POST_MERGE_CONSENSUS_ERROR", r"consensus mechanism|no consensus|ethash|proof.of.stake|terminal.total.difficulty"),
    ("CONFIG_DUPLICATE_OR_INCOMPATIBLE_FORK", r"fork.{0,45}(?:unsupported|error|invalid)|unsupported.{0,40}fork|prague|electra|osaka|fulu"),
    ("GENESIS_ALLOC_ACCOUNT_ERROR", r"genesis account|alloc|invalid account|storage.{0,40}(?:invalid|error)|balance.{0,40}error"),
    ("JAVA_CLI_UNMATCHED_ARGUMENT", r"unmatched arguments?|unrecognized arguments?|unknown option|invalid option|unknown argument|unknown parameter"),
    ("JAVA_CLI_MISSING_ARGUMENT", r"missing required option|missing required parameter|not enough arguments"),
    ("JAVA_STARTUP_FAILED", r"failed to start besu|error starting besu|cannot start besu"),
    ("JAVA_MODULE_CLASSLOADER", r"classloader|class not found|noclassdeffounderror|unsupportedclassversionerror"),
    ("JAVA_LOGGING_INITIALIZATION", r"logging|log4j|appender|logback|slf4j"),
    ("JAVA_TMP_FILE_ACCESS", r"temporary directory|tempdir|java\.io\.tmpdir|/tmp/|accessdeniedexception"),
    ("JAVA_FILESYSTEM_READ_ONLY", r"read.only file.system|erofs|filesystemexception|not writable"),
    ("JAVA_JVM_CRASH_OR_SIGNAL", r"fatal error has been detected|sigsegv|hs_err_pid|segmentation fault|core dump"),
    ("JAVA_NATIVE_LIBRARY_ERROR", r"failed to load native|native library|shared library|unsatisfiedlinkerror"),
    ("JAVA_HOST_RESOLUTION_FAILURE", r"unknownhostexception|unable to resolve|could not resolve hostname"),
    ("JAVA_DATABASE_ERROR", r"rocksdb|database.{0,60}(?:error|failed)|storageexception"),
    ("AUTH_JWT_FAILURE", r"jwt|authentication token|secret file|secret key"),
    ("RPC_HOST_ALLOWLIST_FAILURE", r"host allowlist|host is not allowed|invalid host allowlist"),
    ("DOCKER_INTERNAL_RESOLUTION", r"sse31340-g2-(?:bn|el)|engine rpc|http://sse31340"),
    ("OUT_OF_MEMORY", r"outofmemoryerror|oom|cannot allocate memory"),
    ("EXCEPTION_STACKTRACE_PRESENT", r"(?:caused by:|exception in thread|at [a-z0-9_$.]+\(.*\.java:)"),
)
SIGNATURES = tuple((name, re.compile(expr, re.I)) for name, expr in BESU_DIAGNOSTIC_SIGNATURES)

def safe_besu_exception_signatures(log_output: str) -> dict:
    lines = log_output.splitlines()
    labels = []
    exception_counts = collections.Counter()
    for line in lines:
        for token in JAVA_EXCEPTION_SIGNATURES:
            if token in ("Error", "Exception"):
                continue
            if re.search(r"(?<![A-Za-z0-9_$])" + re.escape(token) + r"(?![A-Za-z0-9_$])", line):
                exception_counts[token] += 1
    categorized = collections.Counter()
    for line in lines:
        for name, expr in SIGNATURES:
            if expr.search(line):
                categorized[name] += 1
    return {
        "knownJavaExceptionNames": [
            {"class": token, "matchedLines": exception_counts[token]}
            for token in JAVA_EXCEPTION_SIGNATURES
            if exception_counts[token]
        ],
        "fixedBesuStartupSignatureCounts": [
            {"signature": name, "matchedLines": categorized[name]}
            for name, _ in SIGNATURES if categorized[name]
        ],
        "unrecognizedExceptionNamesEmitted": False,
        "rawErrorMessagesEmitted": False,
    }

def categorize(log_output: str) -> dict:
    """Public-safe summary only; input can contain arbitrary private text."""
    counts = collections.Counter()
    lines = log_output.splitlines()
    error_lines = 0
    unmatched = 0
    for line in lines:
        if not ERROR_WORDS.search(line):
            continue
        error_lines += 1
        found = [name for name, expr in CATEGORIES if expr.search(line)]
        if found:
            for name in found:
                counts[name] += 1
        else:
            unmatched += 1
    return {
        "logLinesExamined": len(lines),
        "possibleErrorLines": error_lines,
        "unclassifiedPossibleErrorLines": unmatched,
        "errorClassifications": [
            {"category": name, "matchedLines": counts[name]}
            for name, _ in CATEGORIES if counts[name]
        ],
        "rawLogTextEmitted": False,
        "secretsOrKeystoreContentEmitted": False,
    }

def docker(args: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(["sudo", "-n", "docker", *args],
                             capture_output=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    if out.returncode:
        return out.returncode, ""
    return 0, (out.stdout + out.stderr)[:MAX_LOG_BYTES].decode("utf-8", errors="replace")

def gate(sha: str) -> None:
    if not SHA_RE.fullmatch(sha) or os.geteuid() == 0:
        raise ValueError("exact Git SHA and unprivileged owner account required")
    actual = subprocess.check_output(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=ROOT, text=True, timeout=6).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT, text=True, timeout=6).strip()
    if actual != sha or dirty:
        raise ValueError("exact clean GitHub checked-out source required")

def inspect_one(name: str) -> dict:
    result = {"container": name}
    rc, raw = docker(["inspect", "--format", "{{json .State}}", name])
    if rc == 0:
        try:
            state = json.loads(raw)
        except (ValueError, TypeError):
            state = None
        if isinstance(state, dict):
            result["status"] = str(state.get("Status", "unknown"))[:30]
            result["exitCode"] = (
                state.get("ExitCode") if type(state.get("ExitCode")) is int else None
            )
            result["oomKilled"] = state.get("OOMKilled") is True
            result["running"] = state.get("Running") is True
            result["stateErrorPresent"] = bool(state.get("Error"))
        else:
            result["inspectParseFailed"] = True
    else:
        result["containerInspectAccessible"] = False
    rc, logs = docker(["logs", "--tail", "160", "--timestamps", name])
    if rc == 0:
        result["readOnlyClassification"] = categorize(logs)
        result["staticRootCauseHints"] = safe_root_hints(logs)
        if name == "sse31340-g2-el":
            result["staticBesuJavaExceptionSignatures"] = safe_besu_exception_signatures(logs)
    else:
        result["containerLogsAccessible"] = False
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="Safe bounded classification of existing chain31340 Docker failures")
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        gate(args.expected_commit)
        output = {
            "schema": "SSE_R37_G2_EXISTING_CONTAINERS_SAFE_DIAGNOSTIC_V1",
            "sourceGitSha": args.expected_commit,
            "observationUnixUtcSeconds": int(time.time()),
            "readOnly": True,
            "containersCreatedOrStartedByThisCommand": False,
            "privateJWTOrValidatorSecretsRead": False,
            "rawDockerLogsEmitted": False,
            "containers": [inspect_one(name) for name in CONTAINERS],
        }
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print("R37_SAFE_DIAG_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
