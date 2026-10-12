class PfSenseCommandCenterCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
    // Track open/closed states for all four master accordion windows
    this.sectionsOpen = this.sectionsOpen || {
      control: false,
      interfaces: false,
      gateways: false,
      services: false
    };
    this.logHistory = this.logHistory || [
      "[SUCCESS] pfSense Command Engine synchronized successfully.",
      "[INFO] All system monitoring modules active."
    ];
  }

  set hass(hass) {
    this._hass = hass;

    // --- UNIVERSAL AUTO-DISCOVERY ENGINE ---
    const allEntityIds = Object.keys(hass.states);
    
    // Intercept all pfSense metrics and core third-party infrastructure daemons
    const pfEntities = allEntityIds.filter(id => 
      id.startsWith('sensor.pfsense_') || 
      id.startsWith('switch.pfsense_') || 
      id.includes('_service_')
    );

    // Resolve structural system variables cleanly
    const wanIpId = pfEntities.find(id => id.includes('wan_ip_address')) || '';
    const dnsblId = pfEntities.find(id => id.includes('dnsbl_blocks')) || '';
    const ipBlocksId = pfEntities.find(id => id.includes('ip_blocks')) || '';
    const memId = pfEntities.find(id => id.includes('memory_used_percentage')) || '';
    const dhcpId = pfEntities.find(id => id.includes('dhcp_leases_online')) || '';
    const cpuId = pfEntities.find(id => id.includes('cpu_usage') || id.includes('cpu_used_percent')) || '';
    const bootId = pfEntities.find(id => id.includes('system_boottime')) || '';

    const wanIp = wanIpId && hass.states[wanIpId] ? hass.states[wanIpId].state : 'Disconnected';
    const dnsbl = dnsblId && hass.states[dnsblId] ? hass.states[dnsblId].state : '0';
    const ipBlocks = ipBlocksId && hass.states[ipBlocksId] ? hass.states[ipBlocksId].state : '0';
    const memUsed = memId && hass.states[memId] ? hass.states[memId].state : '0';
    const dhcpOnline = dhcpId && hass.states[dhcpId] ? hass.states[dhcpId].state : '0';
    const cpuUsed = cpuId && hass.states[cpuId] ? hass.states[cpuId].state : '0';
    
    let bootTimeStr = 'Unknown';
    if (bootId && hass.states[bootId]) {
      const rawBoot = hass.states[bootId].state;
      bootTimeStr = rawBoot.includes('T') ? rawBoot.replace('T', ' ').substring(0, 16) : rawBoot;
    }

    // Process and sort nested items dynamically
    const interfaces = {};
    const gateways = {};
    const services = [];

    pfEntities.forEach(id => {
      const stateObj = hass.states[id];
      if (!stateObj) return;

      if (id.includes('_interface_') && id.endsWith('_status')) {
        const match = id.match(/_interface_(.*?)_status/);
        if (match) {
          const ifName = match[1];
          interfaces[ifName] = { id: id, status: stateObj.state, props: {} };
          pfEntities.filter(p => p.includes(`_interface_${ifName}_`)).forEach(pId => {
            const propName = pId.split(`_interface_${ifName}_`)[1];
            interfaces[ifName].props[propName] = hass.states[pId].state;
          });
        }
      }

      if (id.includes('_gateway_') && id.endsWith('_status')) {
        const match = id.match(/_gateway_(.*?)_status/);
        if (match) {
          const gwName = match[1];
          gateways[gwName] = { id: id, status: stateObj.state, props: {} };
          pfEntities.filter(p => p.includes(`_gateway_${gwName}_`)).forEach(pId => {
            const propName = pId.split(`_gateway_${gwName}_`)[1];
            gateways[gwName].props[propName] = hass.states[pId].state;
          });
        }
      }

      if (id.startsWith('switch.') && (id.includes('_service_') || id.includes('pfsense_service_'))) {
        services.push({ id: id, state: stateObj.state, friendlyName: stateObj.attributes.friendly_name || id });
      }
    });

    // Draw the main card framework once to guarantee DOM stability
    if (!this.content) {
      this.innerHTML = `
        <style>
          ha-card {
            background: radial-gradient(circle at top left, #0e1726, #05070f);
            color: #f1f5f9;
            font-family: 'SF Pro Display', -apple-system, sans-serif;
            padding: 24px;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
          }
          .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
          }
          .title-area h2 {
            margin: 0; font-size: 22px; font-weight: 800;
            background: linear-gradient(135deg, #ffffff, #94a3b8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            text-transform: uppercase; letter-spacing: 0.5px;
          }
          .title-area p { margin: 4px 0 0 0; font-size: 11px; color: #06b6d4; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }
          .badge {
            padding: 6px 14px; border-radius: 30px; font-size: 11px; font-weight: 800;
            text-transform: uppercase; border: 1px solid rgba(244, 63, 94, 0.2); background: rgba(244, 63, 94, 0.05); color: #f43f5e;
          }
          
          /* METRIC TOP DECK */
          .telemetry-deck { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
          .telemetry-card {
            background: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 14px; padding: 12px 6px; text-align: center; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          }
          .telemetry-card:hover {
            background: rgba(6, 182, 212, 0.03); border-color: rgba(6, 182, 212, 0.4);
            transform: translateY(-2px); box-shadow: 0 8px 20px rgba(6, 182, 212, 0.2);
          }
          .telemetry-card h4 { margin: 0; font-size: 9px; color: #64748b; text-transform: uppercase; }
          .telemetry-card .value { margin: 6px 0 2px 0; font-size: 16px; font-weight: 800; color: #ffffff; font-family: monospace; }
          .telemetry-card .sub { font-size: 10px; color: #06b6d4; font-weight: 600; }

          /* ACCORDION MASTER WRAPPERS */
          .section-accordion {
            background: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 14px; margin-bottom: 12px; overflow: hidden; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          }
          .section-accordion:hover {
            border-color: rgba(6, 182, 212, 0.3); background: rgba(255, 255, 255, 0.02);
            box-shadow: 0 4px 20px rgba(6, 182, 212, 0.05);
          }
          .section-accordion#sec-control:hover {
            border-color: rgba(239, 68, 68, 0.3); box-shadow: 0 4px 20px rgba(239, 68, 68, 0.05);
          }
          .section-trigger {
            display: flex; justify-content: space-between; align-items: center;
            padding: 16px; cursor: pointer; user-select: none;
          }
          .section-title-text {
            font-size: 12px; text-transform: uppercase; color: #94a3b8;
            letter-spacing: 1px; font-weight: 700; display: flex; align-items: center; gap: 8px;
          }
          .section-title-text ha-icon { color: #64748b; transition: all 0.3s; }
          .section-accordion.open .section-title-text ha-icon { color: #06b6d4; filter: drop-shadow(0 0 6px #06b6d4); }
          .section-accordion.open .section-title-text { color: #ffffff; }
          
          /* Custom overrides for the dedicated Control element */
          .section-accordion#sec-control .section-title-text { color: #ef4444; }
          .section-accordion#sec-control .section-title-text ha-icon { color: #ef4444; }
          .section-accordion#sec-control.open .section-title-text ha-icon { filter: drop-shadow(0 0 6px #ef4444); }
          
          .section-dropdown-icon { color: #475569; transition: transform 0.3s ease; }
          .section-accordion.open .section-dropdown-icon { transform: rotate(180deg); color: #06b6d4; }
          .section-accordion#sec-control.open .section-dropdown-icon { color: #ef4444; }
          
          /* CONTENT SLIDER DRAWER */
          .section-content-drawer {
            max-height: 0; overflow: hidden; transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            background: rgba(0, 0, 0, 0.2);
          }
          .section-accordion.open .section-content-drawer {
            max-height: 800px; border-top: 1px solid rgba(255, 255, 255, 0.03);
          }
          .drawer-padding { padding: 16px; display: flex; flex-direction: column; gap: 10px; }

          /* LIST RECORDS ROW STYLING */
          .data-item-row {
            background: rgba(17, 24, 39, 0.4); border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 10px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;
            transition: all 0.25s ease;
          }
          .data-item-row:hover {
            border-color: rgba(255,255,255,0.08); background: rgba(17,24,39,0.6); transform: translateX(2px);
          }
          .data-item-left { display: flex; align-items: center; gap: 12px; }
          .data-item-left h3 { margin: 0; font-size: 13px; font-weight: 700; color: #f1f5f9; text-transform: uppercase; }
          .data-item-left p { margin: 2px 0 0 0; font-size: 11px; color: #64748b; }
          .data-sub-metrics { font-size: 11px; color: #cbd5e1; font-family: monospace; text-align: right; display: flex; flex-direction: column; gap: 2px; }
          .data-sub-metrics span { color: #475569; margin-right: 4px; font-family: sans-serif; font-weight: 600; }

          /* WIRE SERVICE SWITCH GRIDS */
          .switch-deck { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 4px 0; }
          .deck-switch-btn {
            background: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px; padding: 14px 8px; text-align: center; cursor: pointer; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          }
          .deck-switch-btn:hover {
            border-color: rgba(6, 182, 212, 0.5); background: rgba(6, 182, 212, 0.04);
            transform: translateY(-3px); box-shadow: 0 8px 24px rgba(6, 182, 212, 0.2);
          }
          .deck-switch-btn.on { background: rgba(16, 185, 129, 0.02); border-color: rgba(16, 185, 129, 0.25); }
          .deck-switch-btn.on:hover {
            border-color: rgba(16, 185, 129, 0.6); background: rgba(16, 185, 129, 0.06);
            box-shadow: 0 8px 24px rgba(16, 185, 129, 0.25);
          }
          .deck-switch-btn ha-icon { color: #475569; transition: color 0.2s; }
          .deck-switch-btn.on ha-icon { color: #10b981; filter: drop-shadow(0 0 6px #10b981); }
          .deck-switch-btn h5 { margin: 6px 0 2px 0; font-size: 11px; font-weight: 700; color: #94a3b8; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; }
          .deck-switch-btn p { margin: 0; font-size: 9px; font-weight: 800; color: #475569; text-transform: uppercase; }
          .deck-switch-btn.on p { color: #10b981; }

          /* SYSTEM UTILITIES PANEL PACKS */
          .maint-btn-row { display: flex; gap: 10px; width: 100%; }
          .maint-btn {
            flex: 1; padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04); background: rgba(0,0,0,0.35);
            color: #94a3b8; font-size: 11px; font-weight: 700; text-transform: uppercase; cursor: pointer; transition: all 0.25s ease;
            display: flex; align-items: center; justify-content: center; gap: 6px;
          }
          .maint-btn:hover { background: rgba(255,255,255,0.06); color: #ffffff; transform: translateY(-2px); }
          .maint-btn.warn:hover { border-color: #f59e0b; color: #f59e0b; box-shadow: 0 6px 20px rgba(245, 158, 11, 0.2); }
          .maint-btn.danger:hover { border-color: #ef4444; color: #ef4444; box-shadow: 0 6px 20px rgba(239, 68, 68, 0.25); }

          /* CONTROLS HOVER FIELD STYLES */
          .action-panel { background: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.04); border-radius: 16px; padding: 16px; }
          .action-panel h4 { margin: 0 0 12px 0; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700; letter-spacing: 0.5px; }
          .control-group { display: flex; gap: 10px; }
          .control-input { flex-grow: 1; background: #05080f; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 10px 14px; color: #ffffff; font-family: monospace; font-size: 13px; transition: border 0.2s; }
          .control-input:focus { outline: none; border-color: #06b6d4; box-shadow: 0 0 10px rgba(6, 182, 212, 0.15); }
          .action-btn { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 0 18px; font-size: 12px; font-weight: 700; cursor: pointer; transition: all 0.2s; text-transform: uppercase; }
          .action-btn:hover { background: #3b82f6; transform: translateY(-1px); box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3); }
          .action-btn.remove { background: #e11d48; }
          .action-btn.remove:hover { background: #f43f5e; box-shadow: 0 4px 15px rgba(244, 63, 94, 0.3); }
          
          /* TERMINAL STREAMS */
          .stream-container { background: #03060d; border: 1px solid rgba(6, 182, 212, 0.12); border-radius: 14px; padding: 16px; margin-top: 20px; font-family: 'Fira Code', monospace; }
          .stream-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(6, 182, 212, 0.08); padding-bottom: 6px; }
          .stream-title { font-size: 10px; color: #475569; font-weight: 800; }
          .live-dot-container { display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 800; color: #06b6d4; }
          .live-dot { width: 6px; height: 6px; background: #06b6d4; border-radius: 50%; box-shadow: 0 0 8px #06b6d4; animation: blink 1.5s infinite; }
          @keyframes blink { 0%, 100% { opacity: 0.2; } 50% { opacity: 1; } }
          .stream-console { max-height: 75px; overflow-y: auto; font-size: 11px; line-height: 1.6; color: #38bdf8; }
        </style>
        
        <ha-card>
          <div class="header-container">
            <div class="title-area">
              <h2>pfSense Command Center</h2>
              <p>Global Real-Time Telemetry Engine</p>
            </div>
            <div id="block-counter" class="badge">0 BLOCKS SINKHOLED</div>
          </div>

          <div class="telemetry-deck">
            <div class="telemetry-card">
              <h4>Memory</h4>
              <div class="value" id="deck-mem">${memUsed}%</div>
              <div class="sub">RAM Load</div>
            </div>
            <div class="telemetry-card">
              <h4>CPU Load</h4>
              <div class="value" id="deck-cpu">${cpuUsed}%</div>
              <div class="sub">Processor</div>
            </div>
            <div class="telemetry-card">
              <h4>DHCP Leases</h4>
              <div class="value" id="deck-dhcp">${dhcpOnline}</div>
              <div class="sub">Active Clients</div>
            </div>
            <div class="telemetry-card">
              <h4>External IP</h4>
              <div class="value" id="deck-wan" style="font-size: 10px; margin-top: 10px;">${wanIp}</div>
              <div class="sub">Border WAN</div>
            </div>
          </div>

          <div class="section-accordion" id="sec-control">
            <div class="section-trigger">
              <div class="section-title-text">
                <ha-icon icon="mdi:shield-alert-outline"></ha-icon> PFsense Control
              </div>
              <ha-icon icon="mdi:chevron-down" class="section-dropdown-icon"></ha-icon>
            </div>
            <div class="section-content-drawer">
              <div class="drawer-padding">
                <div class="maint-btn-row">
                  <button class="maint-btn warn" id="maint-flush"><ha-icon icon="mdi:database-refresh-outline"></ha-icon>Flush States</button>
                  <button class="maint-btn warn" id="maint-reboot"><ha-icon icon="mdi:restart"></ha-icon>Reboot</button>
                  <button class="maint-btn danger" id="maint-halt"><ha-icon icon="mdi:power"></ha-icon>Halt</button>
                </div>
                <div style="font-size:10px; color:#eab308; margin-top:10px; font-family:monospace; font-weight:700;" id="maint-boottime">BOOTTIME MARKER: ${bootTimeStr}</div>
              </div>
            </div>
          </div>

          <div class="section-accordion" id="sec-interfaces">
            <div class="section-trigger">
              <div class="section-title-text"><ha-icon icon="mdi:lan"></ha-icon> Physical & Virtual Interfaces</div>
              <ha-icon icon="mdi:chevron-down" class="section-dropdown-icon"></ha-icon>
            </div>
            <div class="section-content-drawer"><div class="drawer-padding" id="interfaces-container"></div></div>
          </div>

          <div class="section-accordion" id="sec-gateways">
            <div class="section-trigger">
              <div class="section-title-text"><ha-icon icon="mdi:router-network"></ha-icon> Dynamic Gateway Routing Topology</div>
              <ha-icon icon="mdi:chevron-down" class="section-dropdown-icon"></ha-icon>
            </div>
            <div class="section-content-drawer"><div class="drawer-padding" id="gateways-container"></div></div>
          </div>

          <div class="section-accordion" id="sec-services">
            <div class="section-trigger">
              <div class="section-title-text"><ha-icon icon="mdi:tunnel-vpn"></ha-icon> Daemon Services & Tunnel Protection</div>
              <ha-icon icon="mdi:chevron-down" class="section-dropdown-icon"></ha-icon>
            </div>
            <div class="section-content-drawer"><div class="drawer-padding switch-deck" id="services-container"></div></div>
          </div>

          <div class="action-panel" style="margin-top:16px;">
            <h4>Dynamic Policy Routing & Alias Management</h4>
            <div class="control-group" style="margin-bottom: 10px;">
              <input type="text" id="alias-name" class="control-input" placeholder="Alias Name (e.g. vpn2_enabled, Isolatie)" value="vpn2_enabled">
            </div>
            <div class="control-group">
              <input type="text" id="target-ip" class="control-input" placeholder="Target Device IP Address" value="192.168.1.50">
              <button class="action-btn" id="btn-add">Add</button>
              <button class="action-btn remove" id="btn-rem">Remove</button>
            </div>
          </div>

          <div class="stream-container">
            <div class="stream-header">
              <div class="stream-title">PFSENSE COMPONENT LOG STREAM</div>
              <div class="live-dot-container"><div class="live-dot"></div><span>LIVE FEED</span></div>
            </div>
            <div class="stream-console" id="console-stream"></div>
          </div>
        </ha-card>
      `;
      
      this.content = this.querySelector('#console-stream');
      
      // Hook core routine executors safely
      this.querySelector('#btn-add').addEventListener('click', () => this.fireAliasService('add'));
      this.querySelector('#btn-rem').addEventListener('click', () => this.fireAliasService('remove'));
      this.querySelector('#maint-flush').addEventListener('click', () => this.fireMaintenanceService('reset_state_table', 'FLUSH FIREWALL TABLES'));
      this.querySelector('#maint-reboot').addEventListener('click', () => this.fireMaintenanceService('system_reboot', 'REBOOT APPLIANCE MACHINE'));
      this.querySelector('#maint-halt').addEventListener('click', () => this.fireMaintenanceService('system_halt', 'POWER DOWN AND HALT THE GATEWAY ENGINE'));

      // Bind all four accordion triggers to their layout drawers seamlessly
      ['control', 'interfaces', 'gateways', 'services'].forEach(key => {
        this.querySelector(`#sec-${key} .section-trigger`).addEventListener('click', () => {
          this.sectionsOpen[key] = !this.sectionsOpen[key];
          this.querySelector(`#sec-${key}`).classList.toggle('open', this.sectionsOpen[key]);
        });
      });
    }

    // --- DIRECT HIGH-SPEED TELEMETRY SYNC LOOP ---
    this.querySelector('#deck-mem').innerText = `${memUsed}%`;
    this.querySelector('#deck-cpu').innerText = `${cpuUsed}%`;
    this.querySelector('#deck-dhcp').innerText = dhcpOnline;
    this.querySelector('#deck-wan').innerText = wanIp;
    this.querySelector('#maint-boottime').innerText = `BOOTTIME MARKER: ${bootTimeStr}`;

    // --- POPULATE AND RE-RENDER INTERFACES SUBGRID ---
    const ifContainer = this.querySelector('#interfaces-container');
    if (ifContainer) {
      if (Object.keys(interfaces).length === 0) {
        ifContainer.innerHTML = `<div style="font-size:11px; color:#475569; text-align:center; padding:4px;">No active interfaces tracked.</div>`;
      } else {
        ifContainer.innerHTML = Object.keys(interfaces).map(name => {
          const item = interfaces[name];
          const cleanName = name.toUpperCase();
          const speedIn = item.props['inbytes_kilobytes_per_second'] || '0';
          const speedOut = item.props['outbytes_kilobytes_per_second'] || '0';
          return `
            <div class="data-item-row">
              <div class="data-item-left">
                <ha-icon icon="mdi:ethernet" style="color:#06b6d4;"></ha-icon>
                <div><h3>Link ${cleanName}</h3><p>Physical Port State Tracking</p></div>
              </div>
              <div class="data-sub-metrics">
                <div><span>RX:</span>${speedIn} KB/s</div>
                <div><span>TX:</span>${speedOut} KB/s</div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // --- POPULATE AND RE-RENDER GATEWAYS SUBGRID ---
    const gwContainer = this.querySelector('#gateways-container');
    if (gwContainer) {
      if (Object.keys(gateways).length === 0) {
        gwContainer.innerHTML = `<div style="font-size:11px; color:#475569; text-align:center; padding:4px;">No active gateways discovered.</div>`;
      } else {
        gwContainer.innerHTML = Object.keys(gateways).map(name => {
          const item = gateways[name];
          const cleanName = name.replace('_status', '').toUpperCase();
          const delay = item.props['delay'] || '0 ms';
          const loss = item.props['loss'] || '0%';
          return `
            <div class="data-item-row">
              <div class="data-item-left">
                <ha-icon icon="mdi:swap-horizontal" style="color:#3b82f6;"></ha-icon>
                <div><h3>${cleanName}</h3><p>Gateway Router Backhaul Link</p></div>
              </div>
              <div class="data-sub-metrics">
                <div><span>RTT:</span>${delay}</div>
                <div><span>LOS:</span>${loss}</div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // --- POPULATE AND RE-RENDER SWITCH CONTROL ENGINE DECK ---
    const srvContainer = this.querySelector('#services-container');
    if (srvContainer) {
      if (services.length === 0) {
        srvContainer.innerHTML = `<div style="font-size:11px; color:#475569; text-align:center; padding:4px; grid-column:span 3;">No network switches found.</div>`;
      } else {
        srvContainer.innerHTML = services.map(srv => {
          const isActive = srv.state === 'on';
          let label = srv.friendlyName.replace('pfSense ', '').replace('Service ', '').replace('status', '').replace('Status', '').trim();
          return `
            <div class="deck-switch-btn ${isActive ? 'on' : ''}" data-id="${srv.id}">
              <ha-icon icon="${isActive ? 'mdi:toggle-switch' : 'mdi:toggle-switch-off-outline'}"></ha-icon>
              <h5>${label}</h5><p>${srv.state}</p>
            </div>
          `;
        }).join('');

        // Wire service call bindings cleanly back to Home Assistant platform core
        this.querySelectorAll('.deck-switch-btn').forEach(btn => {
          btn.addEventListener('click', (e) => {
            const entId = e.currentTarget.getAttribute('data-id');
            const currentState = e.currentTarget.querySelector('p').innerText;
            const targetService = currentState === 'on' ? 'turn_off' : 'turn_on';
            const targetName = e.currentTarget.querySelector('h5').innerText;
            
            if (confirm(`CRITICAL INFRASTRUCTURE WARNING:\nAre you sure you want to change network routing state for: ${targetName}?`)) {
              this.addLogEntry(`[DAEMON] Modifying service path: ${targetName} -> ${targetService.toUpperCase()}`);
              this._hass.callService('switch', targetService, { entity_id: entId });
            }
          });
        });
      }
    }

    const totalBlocks = parseInt(dnsbl) + parseInt(ipBlocks);
    this.querySelector('#block-counter').innerText = `${totalBlocks} BLOCKS SINKHOLED`;
    this.renderConsole();
  }

  addLogEntry(message) {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
    this.logHistory.unshift(`[${timestamp}] ${message}`);
    if (this.logHistory.length > 15) this.logHistory.pop();
    this.renderConsole();
  }

  renderConsole() {
    if (!this.content) return;
    this.content.innerHTML = this.logHistory.map(line => `<div class="stream-line">${line}</div>`).join('');
  }

  async fireMaintenanceService(serviceName, warningText) {
    const allEntityIds = Object.keys(this._hass.states);
    const fallbackEntity = allEntityIds.find(id => id.startsWith('sensor.pfsense_') && id.includes('wan_ip_address')) || '';
    
    if (!confirm(`CRITICAL APPLIANCE ALERT:\nAre you sure you want to execute command:\n-> [ ${warningText} ]?\n\nThis will instantly disrupt local network traffic.`)) {
      return;
    }
    
    this.addLogEntry(`[MAINTENANCE] Firing system executive instruction: ${serviceName.toUpperCase()}`);
    try {
      await this._hass.callService('pfsense', serviceName, { entity_id: fallbackEntity });
      this.addLogEntry(`[SUCCESS] Instruction handled by pfSense API Client.`);
    } catch(err) {
      this.addLogEntry(`[ERROR] Maintenance execution call dropped: ${err.message}`);
    }
  }

  async fireAliasService(actionType) {
    const aliasName = this.querySelector('#alias-name').value.trim();
    const targetIp = this.querySelector('#target-ip').value.trim();
    const allEntityIds = Object.keys(this._hass.states);
    const fallbackEntity = allEntityIds.find(id => id.startsWith('sensor.pfsense_') && id.includes('wan_ip_address')) || '';
    
    if (!aliasName || !targetIp) {
      this.addLogEntry(`[WARNING] Input validation failed. Check parameter syntax variables.`);
      return;
    }

    if (!confirm(`SECURITY ALERT: Alter alias tracking configuration row?\nTable: ${aliasName}\nTarget address: ${targetIp}\nOperation: ${actionType.toUpperCase()}`)) {
      return;
    }

    this.addLogEntry(`[PENDING] Modifying table '${aliasName}': ${actionType.toUpperCase()} -> ${targetIp}`);
    try {
      await this._hass.callService('pfsense', 'update_alias', {
        entity_id: fallbackEntity,
        alias_name: aliasName,
        address: targetIp,
        action: actionType,
        kill_states: true
      });
      this.addLogEntry(`[SUCCESS] Table written. Active states matching ${targetIp} terminated.`);
    } catch (err) {
      this.addLogEntry(`[ERROR] API transmission error: ${err.message}`);
    }
  }

  getCardSize() {
    return 8;
  }
}

customElements.define('pfsense-command-center-card', PfSenseCommandCenterCard);