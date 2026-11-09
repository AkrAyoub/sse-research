#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v forge >/dev/null || { echo 'Foundry missing. On native Windows, install Foundry in Git Bash using Foundry installation first.' >&2; exit 1; }
mkdir -p lib
if [[ ! -f lib/forge-std/src/Test.sol ]]; then forge install --no-git foundry-rs/forge-std@v1.9.5; fi
if [[ ! -f lib/openzeppelin-contracts/contracts/utils/cryptography/EIP712.sol ]]; then forge install --no-git OpenZeppelin/openzeppelin-contracts@v5.0.2; fi
printf '%s\n' 'Contract dependencies installed'
