# Plastic Slinger for Home Assistant

Shows active, paused, recently completed, and failed 3D prints in Home Assistant from your self-hosted **Plastic Slinger**
print farm manager, proxies printer camera snapshots through Home Assistant's authenticated HTTP pipeline (including the
held last camera frame when a completed printer powers off at its smart plug), and lets you control active prints and clear
finished prints right from your dashboard.

Home Assistant talks only to Plastic Slinger on your LAN (with an API key created under **Settings → API keys**); nothing
outside Plastic Slinger talks to your printers directly.

The dashboard card that renders the 2-column 16:9 camera glance grid and native printer control modal,
`plastic-slinger-glance-card`, lives in its own repository,
[Plastic-Slinger-HA-Card](https://github.com/TopHATTwaffle/Plastic-Slinger-HA-Card).

## What you get

- A device (**Plastic Slinger**) and an **Active prints** sensor (`sensor.plastic_slinger_active_prints`). Its state is
  the number of printers currently shown on the glance view (printing, paused, recently completed, or failed). Its
  attributes carry everything the `plastic-slinger-glance-card` needs:
  - `printers`: pre-sorted list of active/held tiles (`id`, `name`, `machine_type`, `nozzle_variant`, `status`,
    `status_label`, `progress_percent`, `remaining_seconds`, `sub_text`, `file_name`, `is_powered_off`, `can_dismiss`,
    `ended_at_ts`, `camera_rotation`, `camera_flip_h`, `camera_flip_v`, `nozzle_temp`, `nozzle_target`, `bed_temp`,
    `bed_target`, `chamber_temp`, `current_layer`, `total_layers`, `has_chamber_light`, `chamber_light_on`,
    `can_auto_unload`, `auto_unload_mode`, `can_skip_parts`, `bed_bounds`, `print_objects`), ordered by your **Glance
    sort order** setting (`Default` or `CompletionTime`).
  - `status_colors`: `{ printing, complete, paused, failed }` from **Settings → Printer status colors & active prints
    glance**, so changing status colors in the app updates the card automatically.
  - `printing_count`, `paused_count`, `complete_count`, `failed_count`, `sort_mode`, and `generated_at`.
  - `printers` and `status_colors` are excluded from the Home Assistant recorder so history stays small.
- An authenticated snapshot proxy endpoint (`/api/plastic_slinger/snapshot/<printer_id>`) that serves each printer's
  JPEG camera snapshot (or its held last frame when powered off) through Home Assistant's own session/bearer
  authentication, so camera images load natively in the Home Assistant Companion App over 5G+ / public internet without
  iframes or Ingress cookies.
- Actions for the card and automations:
  - `plastic_slinger.dismiss_print` (`printer_id`): clears a held completed or failed print from the glance view.
  - `plastic_slinger.pause_print` (`printer_id`): pauses the active print.
  - `plastic_slinger.resume_print` (`printer_id`): resumes a paused print.
  - `plastic_slinger.cancel_print` (`printer_id`): cancels the active or paused print.
  - `plastic_slinger.set_light` (`printer_id`, optional `on`): sets or toggles the chamber light.
  - `plastic_slinger.set_auto_unload` (`printer_id`, optional `mode`: `off`, `once`, `always`): sets or cycles auto-unload after print.
  - `plastic_slinger.skip_parts` (`printer_id`, `names`): skips one or more parts (`EXCLUDE_OBJECT`) on a Klipper/Moonraker print.

## Install

**HACS:** add `https://github.com/TopHATTwaffle/Plastic-Slinger-HA` in HACS → ⋮ → Custom repositories (category
*Integration*), install **Plastic Slinger**, and restart Home Assistant.

**Manually:** copy `custom_components/plastic_slinger` into your Home Assistant `config/custom_components/` folder and
restart.

## Set up

1. In Plastic Slinger: **Settings → API keys → Create key** (name it e.g. "Home Assistant"). Copy the key (it starts
   with `ps_` and is only shown once).
2. In Home Assistant: **Settings → Devices & services → Add integration → Plastic Slinger**. Enter the LAN address of
   Plastic Slinger (e.g. `http://plasticslinger.example.lan:6060`) and the API key. Turn off *Verify the SSL
   certificate* only if using HTTPS with a self-signed certificate.
3. Optional: **Configure** sets how often Home Assistant polls Plastic Slinger (default 5 s, 2–300).

If the API key is revoked in the app, Home Assistant prompts for a new one (re-authentication).

If Plastic Slinger is briefly unreachable (for example while restarting during a deploy), the sensor keeps its last
values for up to 2 minutes so dashboards don't flicker.

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```
