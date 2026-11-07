# AES key wrapper — security specification

## Overview

`aes_key_wrapper` sits between the system bus and an AES core. It stores one 128-bit key
in four 32-bit key registers, exposes a control/status register, and provides a debug
read-back path for manufacturing test.

Bus interface: 8-bit address, 32-bit data, `wr_en`, `rd_en`, `priv` (1 = privileged master).

## Register map

| Address | Name      | Access                | Notes                                   |
|---------|-----------|-----------------------|-----------------------------------------|
| 0x00    | CTRL      | RW (privileged only)  | bit0 `key_valid`, bit1 `debug_lock`      |
| 0x04    | STATUS    | RO                    | bit0 `busy`                              |
| 0x10    | KEY0      | WO (privileged only)  | key[31:0]                                |
| 0x14    | KEY1      | WO (privileged only)  | key[63:32]                               |
| 0x18    | KEY2      | WO (privileged only)  | key[95:64]                               |
| 0x1C    | KEY3      | WO (privileged only)  | key[127:96]                              |

## Security assets

- **A1 — Key register bank** (`key_q`): must never be observable through any read path on
  the system bus or the debug interface once `debug_lock` is set.
- **A2 — `debug_lock` bit**: write-once per reset. Once set it cannot be cleared by software.
- **A3 — Privilege boundary**: CTRL and KEY registers accept writes only when `priv` is high.

## Security requirements

- **SR1.** Reads from any KEY address return `32'h0` regardless of privilege.
- **SR2.** The debug read-back port (`dbg_rd_addr`, `dbg_rd_data`) returns the key words
  only while `debug_lock == 0`. When `debug_lock == 1` it returns `32'h0`.
- **SR3.** `debug_lock` is sticky: writing CTRL with bit1 = 0 after it has been set has no
  effect on the bit until the next reset.
- **SR4.** Writes to CTRL or KEY registers with `priv == 0` are ignored and set the
  `access_err` status output for one cycle.
- **SR5.** Setting `key_valid` while the AES core is `busy` is ignored.

## Threat model inputs

- Unprivileged software on the system bus.
- A manufacturing test harness with access to the debug port after the device has been
  provisioned (debug_lock set by firmware before any untrusted code runs).
