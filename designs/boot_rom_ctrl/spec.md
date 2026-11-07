# Boot ROM controller — security specification

## Overview

`boot_rom_ctrl` gates access to a 4 KiB boot ROM and a 256-byte ROM patch RAM. During the
boot phase, trusted firmware may write patch entries. Once firmware signals that boot has
finished, the patch RAM becomes immutable and the controller only serves reads.

Bus interface: 12-bit address, 32-bit data, `wr_en`, `rd_en`. The controller has two resets:
`por_n` (power-on reset) and `warm_rst_n` (software-triggered warm reset).

## Register map

| Address | Name       | Access | Notes                                             |
|---------|------------|--------|---------------------------------------------------|
| 0xF00   | BOOT_CTRL  | RW     | bit0 `boot_done`, write-once                      |
| 0xF04   | PATCH_CNT  | RO     | number of patch entries written                   |
| 0xE00–0xEFF | PATCH  | RW during boot, RO after | patch RAM                       |
| 0x000–0xDFF | ROM    | RO     | boot ROM                                          |

## Security assets

- **A1 — `boot_done` bit**: the root of trust transition. Once set it must remain set until
  the next power-on reset.
- **A2 — Patch RAM contents**: immutable after `boot_done`.
- **A3 — Boot ROM**: never writable.

## Security requirements

- **SR1.** `boot_done` is write-once. Writes to BOOT_CTRL after `boot_done == 1` are ignored.
- **SR2.** `boot_done` is cleared only by `por_n`. A warm reset must not clear it.
- **SR3.** Writes to the PATCH region while `boot_done == 1` are dropped and raise
  `patch_wr_err` for one cycle.
- **SR4.** Writes to the ROM region are always dropped and raise `patch_wr_err`.
- **SR5.** The first write of `boot_done = 1` takes effect in the same cycle it is accepted,
  so a PATCH write presented in the following cycle is already rejected.

## Threat model inputs

- Untrusted application code running after boot, able to issue arbitrary bus transactions
  and request warm resets.
