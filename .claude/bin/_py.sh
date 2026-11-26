#!/usr/bin/env bash
# Portability shim: Git Bash on Windows commonly ships `python` but not
# `python3`. Every np script that needs an interpreter goes through here.
exec "$(command -v python3 || command -v python)" "$@"
