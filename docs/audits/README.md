# Audit records

Process documentation beyond the commit history. This project is built by
an LLM coding agent under human direction (see the release notes'
provenance sections); part of demonstrating that workflow is leaving a
precise historic record of *how* defects were found — the methodology,
the dead ends, and the ground truth behind each claim — not just the
fixes that landed. Reviewers who want to go deeper than the diff start
here.

Each audit ships as a narrative report (`.md`) plus a structured findings
ledger (`.json`) with severities, evidence and commit hashes.

## Records

- **2026-07-12 — 0.5 deep audit.** Second pass over the container split:
  static integrity, tri-mode live comparison, failure injection on real
  hardware. 15 findings.
- **2026-07-12 — consolidation pass.**
- **2026-07-18 — fastboot power, charging, and exact watch identity.**
  Hardware ground truth for the bootloader: what charges, what powers off,
  what the `oem` table actually contains, and how a watch's true codename
  can be read when it shares a sibling's image. 14 findings, including
  three claims this project's own assistant got wrong the same day and the
  mechanism of each error, and one operator error that destroyed a running
  measurement.

Findings are **version-stamped** with the firmware measured. A capability
claim is only true for a given build; undated ones are the most likely
reason published hardware tables drift out of truth.
