# Hardware Findings

## USB Hubs — PPPS behaviour

### ALCOR 05e3:0606 "USB Hub 2.0" (all four docked hubs, 2026-07-01/02)

**Verdict: data-line disconnect only. NOT true VBUS switching.**

- uhubctl identifies as `ppps`, all commands exit 0, port correctly shows `0000 off`
- VBUS (5V) stays live on the port pin regardless of switch state
- USB data lines (D+/D−) are disconnected: ADB drops, device vanishes from USB enumeration
- Watch continues charging while port shows `off`
- Consequence: charge timer non-functional with these hubs

**Diagnostic test used:** switch port off via uhubctl, observe whether watch screen shows
charging indicator. It did. Confirmed on multiple ports across multiple hubs.

**Useful for:** ADB operations (reboot, bootloader, flash) — these need data lines only.
**Not useful for:** battery management, stopping/starting charging.

---

### "Manhattan Mondo Hub" (tested 2026-07-02, brand/model LOST TO COMPACTION)

**Verdict: also data-line only.** Initially appeared promising — LEDs blinked during
cycle test, suggesting real power switching. But VBUS stayed live when port was switched
off. Same failure mode as ALCOR hubs.

**TODO:** Ask user to confirm brand/model so this entry can be completed.

---

## What to buy for true VBUS switching

Reference: https://github.com/mvp/uhubctl#compatible-usb-hubs

Confirmed options:
- **Yepkit YKUSH** — explicit VBUS control, confirmed working with uhubctl
- **Acroname USB 3.1** — gold standard, expensive
- Various Via Labs / Terminus USB 3 hubs — check the compatibility list

---

## uhubctl permissions on w541

Running as user `mo` (systemd user service, no sudo):
- sysfs path (`/sys/bus/usb/devices/.../disable`) requires root → permission denied
- uhubctl falls back to libusb automatically, exit code 0, switching works
- Spurious "Permission denied / Falling back to libusb" warning was going to stderr
  → fixed by adding `-S` flag to `uhubctl_set_power()` call (commit f69379d)
- Full udev sysfs rules are in `udev/70-asteroid-docking-bay.rules` (05e3 line commented out)
  — could be uncommented and installed to allow sysfs path too, but libusb works fine

---

## Watch inventory (as of 2026-07-02)

| codename | serial           | hub | port | device              | notes |
|----------|-----------------|-----|------|---------------------|-------|
| sturgeon | MQB7N15C09000847 | 1-6 | 3    |                     | |
| catfish  | 720EX8C130737    | 1-3 | 3    | Mobvoi TicWatch Pro | |
| skipjack | 870AX0A150253    | 1-2 | 3    | Mobvoi TicWatch C2+ | |
| narwhal  | 901KPRW0013510   | 1-1 | 2    | LG Watch W7         | was moved to mondo hub for test, may need remap |
| sawfish  | TKQ7N17406001852 | 1-1 | 3    | HUAWEI LEO-BX9      | |
| beluga   | 100c0a32         | —   | —    |                     | in serials dict, not mapped |
