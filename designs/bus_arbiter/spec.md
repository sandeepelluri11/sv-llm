# Two-master bus arbiter — security specification

## Overview

`bus_arbiter` grants a shared peripheral bus to one of two masters. Master 0 is the secure
core; master 1 is the application core. A master may assert `lock` together with `req` to
hold the bus across multiple transfers (for example, a read-modify-write on a peripheral).

## Interface

| Signal              | Dir | Notes                                              |
|---------------------|-----|----------------------------------------------------|
| `req[1:0]`          | in  | request per master                                 |
| `lock[1:0]`         | in  | request an atomic hold per master                  |
| `grant[1:0]`        | out | one-hot grant                                      |
| `secure_only_lock`  | in  | configuration: when 1, only master 0 may lock      |
| `lock_timeout`      | out | pulses when a lock hold is forcibly released       |

## Security assets

- **A1 — Bus availability for the secure core**: master 0 must always be able to obtain the
  bus within a bounded number of cycles.
- **A2 — Atomicity of secure sequences**: while master 0 holds a lock, master 1 must not be
  granted.
- **A3 — Lock privilege**: when `secure_only_lock == 1`, `lock[1]` must be ignored.

## Security requirements

- **SR1.** Arbitration is round-robin between the two masters when neither holds a lock.
- **SR2.** A locked grant is held while the owner keeps `req` and `lock` asserted.
- **SR3.** A locked grant is held for at most 16 consecutive cycles. On the 17th cycle the
  arbiter drops the grant, pulses `lock_timeout`, and re-arbitrates.
- **SR4.** When `secure_only_lock == 1`, `lock[1]` is treated as 0.
- **SR5.** `grant` is never `2'b11`.

## Threat model inputs

- Malicious or compromised software on the application core (master 1) attempting to starve
  the secure core or to interleave transfers into a secure read-modify-write sequence.
