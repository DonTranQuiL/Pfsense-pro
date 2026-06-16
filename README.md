# 🛡️ pfSense-Pro
**The high-performance, real-time perimeter security, telemetry, and dynamic policy routing platform for Home Assistant.**

> ⚠️ **LATEST ARCHITECTURAL REWRITE ANNOUNCEMENT**
>
> This project is a complete, ground-up rewrite! We have successfully migrated to a Dynamic Entity Auto-Discovery Engine. The integration now features an optimized XML-RPC non-blocking mutex pipeline, a protective storage smart-cache system, direct browser DOM-injection counters to prevent dashboard freezing, and an instantaneous connection State-Killing matrix.

[![Latest Release](https://img.shields.io/github/v/release/DonTranQuiL/Pfsense-pro?style=for-the-badge&color=007ec6)](https://github.com/DonTranQuiL/Pfsense-pro/releases)
[![License](https://img.shields.io/github/license/DonTranQuiL/Pfsense-pro?style=for-the-badge&color=007ec6)](https://github.com/DonTranQuiL/Pfsense-pro/blob/main/LICENSE)
[![Home Assistant CI](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Pfsense-pro/hass-ci.yml?label=Home%20Assistant%20CI&style=for-the-badge)](https://github.com/DonTranQuiL/Pfsense-pro/actions/workflows/hass-ci.yml)
[![Code Checks](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Pfsense-pro/codechecker.yml?style=for-the-badge&label=CODE%20CHECKS&color=5dbb0f)](https://github.com/DonTranQuiL/Pfsense-pro/actions)
[![Tests](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Pfsense-pro/pytest.yml?style=for-the-badge&label=TESTS&color=5dbb0f)](https://github.com/DonTranQuiL/Pfsense-pro/actions)
[![HACS Validation](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Pfsense-pro/hacs.yaml?style=for-the-badge&label=HACS%20VALIDATION&color=5dbb0f)](https://github.com/DonTranQuiL/Pfsense-pro/actions)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-5dbb0f?style=for-the-badge)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=for-the-badge)](https://github.com/astral-sh/ruff)
[![HACS Custom](https://img.shields.io/badge/HACS-CUSTOM-ff6e27?style=for-the-badge)](https://hacs.xyz/)
[![Home Assistant Version](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-007ec6?style=for-the-badge)](https://www.home-assistant.io/)
[![Maintainer](https://img.shields.io/badge/maintainer-%40DonTranQuiL-007ec6?style=for-the-badge)](https://github.com/DonTranQuiL)
[![Donate](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-ffdd00?style=for-the-badge)](https://ko-fi.com/DonTranQuiL)
[![Community Forum](https://img.shields.io/badge/community-forum-007ec6?style=for-the-badge)](https://community.home-assistant.io/t/ads-b-tracker-for-home-assistant/1011081)

</div>
---

# 🚨 Real-Time Perimeter Intelligence & Orchestration

Bring hyper-fast, live firewall diagnostics, packet drop counters, and active interface throughput tracking directly into Home Assistant.

Engineered for low-overhead edge networks, this platform allows you to execute on-the-fly multi-table alias swaps, manage core daemon service states, and isolate rogue client nodes with instantaneous execution.

---

# 📥 Installation

## Method 1: HACS (Recommended)

The most efficient deployment method is through HACS (Home Assistant Community Store):

1. Open **HACS** in your sidebar and navigate into the **Integrations** panel.
2. Click the three dots (`...`) located in the upper right quadrant and select **Custom repositories**.
3. Input the repository web link:

```text
https://github.com/DonTranQuiL/pfsense-pro
```

4. Set the **Category** selector dropdown to **Integration** and hit **Add**.
5. Locate the newly added **pfSense Pro** repository card and hit **Download**.

> ⚠️ Restart your Home Assistant instance to flush internal class caches.

6. Navigate to:

```text
Settings → Devices & Services → Add Integration
```

7. Search for **pfSense** and complete the initial setup form:
   - URL
   - Username
   - Password

---

## Method 2: Manual Installation

1. Download the latest release from the Releases page.
2. Extract the `pfsense` folder into your Home Assistant `custom_components` directory.

> ⚠️ Restart your Home Assistant instance.

3. Configure via:

```text
Settings → Devices & Services → Add Integration
```

---

# ⚙️ Interactive Lovelace Command Center Dashboard Card

<img width="813" height="802" alt="pfsensecommand" src="https://github.com/user-attachments/assets/8f9cdd3c-f4d6-481a-98af-72a92ffd3106" />

To achieve the full NOC (Network Operations Center) visual experience, you must install the custom frontend architecture.

This is not a standard YAML card—it is a high-performance JavaScript module utilizing direct DOM-injection to prevent dashboard stalling.

## Premium UI Highlights

### Direct DOM-Injection

High-frequency metrics (CPU, RAM, DHCP Leases) bypass Home Assistant's standard template re-rendering loops.

Data ticks freely in the UI without causing text-focus drops or browser freezes.

### Animated Accordion Drawers

Major sub-sections:

- Interfaces
- Gateways
- Daemons

slide open beautifully on a single click while keeping your dashboard pristine.

### PFsense Control Module

A specialized, stealthy dropdown panel built to hold critical system execution scripts:

- Flush State Tables
- Reboot Router
- Halt Appliance

### Double-Verification Guardrails

Tapping any daemon toggle (e.g. WireGuard/Tailscale) or appliance recovery script throws a native browser `confirm()` prompt, protecting your home network from accidental downtime.

### Live Operational Syslog Feed

A stylized cyber-terminal event box tracking and displaying:

- API calls
- Alias pool variations
- Security sinks

in real time.

---

# Installation Instructions

1. Connect to your Home Assistant file system (via SSH, Samba, or File Editor).
2. Navigate to:

```text
/config/www/
```

3. Create a new file named:

```text
pfsense-command-center.js
```

4. Paste the frontend JavaScript code into the file.

5. In Home Assistant navigate to:

```text
Settings → Dashboards → Three Dots (Top Right) → Resources
```

6. Click **+ Add Resource**

Set:

```text
URL:
/local/pfsense-command-center.js

Resource Type:
JavaScript Module
```

7. Go to your dashboard.
8. Click **Edit Dashboard**.
9. Add a **Manual Card**.
10. Paste the following zero-config trigger:

```yaml
type: custom:pfsense-command-center-card
```

---

# 🧠 Core Pipeline Mechanics Reference Wiki

To harness the true power of pfSense Pro, network administrators must understand how the dynamic alias modification pipeline and outbound connection state-killing engines operate under the hood.

```text
┌─────────────────────────┐               ┌──────────────────────────┐               ┌───────────────────────────┐
│ Home Assistant UI Card  │  ───────────> │  Services Mapping Layer  │  ───────────> │  pypfsense Client Engine  │
│ [Alias / Target Input]  │               │    [services.py Patch]   │               │    [pypfsense/__init__.py]│
└─────────────────────────┘               └──────────────────────────┘               └───────────────────────────┘
                                                                                                   │
                                                                                                   ▼
                                                                                     [Secure XML-RPC Remote Script Execution]

┌─────────────────────────┐               ┌──────────────────────────┐               ┌───────────────────────────┐
│ Active Sessions Cleared │ <───────────  │ Background Filter Reload │ <───────────  │ config.xml Array Appended │
│  [pfctl State Purge]    │               │    [filter_configure()]  │               │ [Array Nesting Normalized]│
└─────────────────────────┘               └──────────────────────────┘               └───────────────────────────┘
```

---

# 1. Dynamic Firewall Aliases (`update_alias`)

In pfSense, an Alias acts as a named bucket of host IPs.

By itself, it performs no actions.

You must link the alias to a static rule in your pfSense WebGUI (for example, route alias through VPN or block alias from WAN) exactly once.

Home Assistant then takes over as the dynamic engine.

When a service call is executed, the client triggers an enterprise-grade operational pipeline:

### JSON Payload Injection

Home Assistant formats and passes your target IP and Alias name into the backend wrapper.

### XML-RPC Transmission

A custom, secured PHP string is passed to the pfSense `xmlrpc.php` target endpoint.

### Array Normalization

pfSense natively stores single-IP aliases as flat strings, but multi-IP aliases as indexed arrays.

The integration intercepts this and dynamically normalizes the array structure to prevent parsing crashes.

### Disk Serialization

The engine:

1. Updates the internal table.
2. Serializes the memory state back onto local disk via `write_config()`.
3. Triggers a lightweight ruleset rebuild via `filter_configure()`.

---

# 2. Zero-Latency State-Killing Engine (`kill_states`)

Standard policy-routing adjustments suffer from session persistence delays.

Active network connections remain locked to their old gateway paths until state table timers naturally expire.

pfSense Pro resolves this completely.

When modifying an alias entry, the engine executes a rapid connection state purge inside the firewall shell:

```bash
/sbin/pfctl -k [target_device_ip]
/sbin/pfctl -k 0.0.0.0/0 -k [target_device_ip]
```

### Command 1 (`-k source`)

Breaks every active socket where your target client machine is the originator.

### Command 2 (`-k source -k dest`)

Clears inbound path echoes.

### The Result

The device experiences a clean, instantaneous socket reset.

When it automatically retries its connection a millisecond later, the newly reloaded firewall rules catch the session and push it down your new VPN tunnel or isolation path instantly.

---

# 🤖 Advanced Automation Staging

Leverage the true power of Home Assistant by tying the pfSense Pro alias manipulation engine directly into your smart-home telemetry.

---

## Rule Integration Pattern A: Automated Intrusion Segment Isolation

Protect your infrastructure.

Instantly drop a suspicious client machine out of your main network and lock it into a strict firewall isolation bucket if a security sensor logs anomalous LAN activities.

```yaml
alias: "Security Matrix: Critical Boundary Node Isolation"

trigger:
  - platform: state
    entity_id: binary_sensor.perimeter_intrusion_alert
    to: "on"

action:
  - service: pfsense.update_alias
    data:
      entity_id: sensor.pfsense_pfsense_local_wan_ip_address
      alias_name: "Isolatie"
      address: "{{ state_attr('device_tracker.suspicious_client_node', 'ip_address') }}"
      action: "add"
      kill_states: true
```

---

## Rule Integration Pattern B: Dynamic VPN Tunnel Scheduling Toggle

Enforce strict routing schedules.

Automatically redirect streaming boxes, game consoles, or local workstations out of your unencrypted ISP gateway and straight into your secure `vpn2_enabled` tunnel at specific times of the day.

```yaml
alias: "Network Optimization: Scheduled Workstation VPN Redirect"

trigger:
  - platform: time
    at: "08:00:00"

action:
  - service: pfsense.update_alias
    data:
      entity_id: sensor.pfsense_pfsense_local_wan_ip_address
      alias_name: "vpn2_enabled"
      address: "192.168.1.120"
      action: "add"
      kill_states: true
```

---

# 🤝 Credits & Attribution

A profound thank you and deep respect goes out to **Travis Hansen (@travisghansen)** and the extensive line of repository contributors who built the initial upstream framework located at:

```text
travisghansen/hass-pfsense
```

Their early pioneering developments paved the way for local XML-RPC network routing control inside the Home Assistant smart-home ecosystem, making this highly-optimized rewrite possible.

---

## Disclaimer

pfSense® is a registered trademark of Rubicon Communications, LLC (Netgate).

This project is an independent Home Assistant integration and is not affiliated with, endorsed by, or sponsored by Netgate.
