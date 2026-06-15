import json
import logging
import re
import ssl
from urllib.parse import quote_plus, urlparse
from xml.parsers.expat import ExpatError
import xmlrpc.client

_LOGGER = logging.getLogger(__name__)

def dict_get(data: dict, path: str, default=None):
    path_list = path.split(".")
    result = data
    for key in path_list:
        try:
            key = int(key) if key.isnumeric() else key
            result = result[key]
        except (KeyError, TypeError, IndexError):
            result = default
            break
    return result

def normalize_service_data(service):
    if isinstance(service, dict):
        pass
    elif service is None:
        service = {}
    elif isinstance(service, str):
        if len(service) > 0:
            service = json.loads(service)
        else:
            service = {}
    else:
        raise TypeError(f"Invalid datatype for variable `service`: {type(service).__name__}")
    return service

class Client(object):
    """pfSense Client - GOLDEN BUILD VERSION (Safe & Synchronous)"""

    def __init__(self, url, username, password, opts=None):
        if opts is None:
            opts = {}

        self._username = username
        self._password = password
        self._opts = opts
        parts = urlparse(url.rstrip("/") + "/xmlrpc.php")
        self._url = "{scheme}://{username}:{password}@{host}/xmlrpc.php".format(
            scheme=parts.scheme,
            username=quote_plus(username),
            password=quote_plus(password),
            host=parts.netloc,
        )
        self._url_parts = urlparse(self._url)

    def _get_proxy(self):
        context = None
        verify_ssl = True
        if "verify_ssl" in self._opts:
            verify_ssl = self._opts["verify_ssl"]

        if self._url_parts.scheme == "https" and not verify_ssl:
            context = ssl._create_unverified_context()

        return xmlrpc.client.ServerProxy(self._url, context=context, verbose=False)

    def _log_errors(func):
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseException as err:
                _LOGGER.error(f"Unexpected {func.__name__} error {err=}, {type(err)=}")
                raise err
        return inner

    def _get_config_section(self, section):
        response = self._get_proxy().pfsense.backup_config_section([section])
        return response[section]

    def _restore_config_section(self, section_name, data):
        params = {section_name: data}
        response = self._get_proxy().pfsense.restore_config_section(params, 60)
        return response

    def _exec_php(self, script):
        script = f"""
ini_set('display_errors', 0);
{script}
$toreturn_real = $toreturn;
$toreturn = [];
$toreturn["real"] = json_encode($toreturn_real);
"""
        response = self._get_proxy().pfsense.exec_php(script)
        return json.loads(response["real"])

    def _exec_command(self, command, background=False):
        script = f"""
$data = json_decode('{json.dumps({"command": command, "background": background})}', true);
if ($data["background"]) {{
    $ret = mwexec_bg($data["command"]);    
}} else {{
    $ret = mwexec($data["command"]);
}}
$toreturn = ["data" => $ret];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_host_firmware_version(self):
        return self._get_proxy().pfsense.host_firmware_version(1, 60)

    @_log_errors
    def get_firmware_update_info(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
require_once '/etc/inc/pkg-utils.inc';
$toreturn = ["data" => ["base" => get_system_pkg_version(), "packages" => []]];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def upgrade_firmware(self):
        script = """
$ret = mwexec_bg("pfSense-upgrade -y -l /tmp/hass-upgrade.log -p /tmp/hass-upgrade.sock");
$toreturn = ["data" => $ret];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def pid_is_running(self, pid):
        script = f"""
$data = json_decode('{json.dumps({"pid": pid})}', true);
$running = posix_kill($data["pid"],0);
$toreturn = ["data" => $running];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_system_serial(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$toreturn = ["data" => system_get_serial()];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_netgate_device_id(self):
        script = """$toreturn = ["data" => system_get_uniqueid()];"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_system_info(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
global $config;
$toreturn = [
  "hostname" => $config["system"]["hostname"],
  "domain" => $config["system"]["domain"],
  "serial" => system_get_serial(),
  "netgate_device_id" => system_get_uniqueid(),
  "platform" => system_identify_specific_platform(),
];
"""
        return self._exec_php(script)

    @_log_errors
    def get_config(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
global $config;
$toreturn = ["data" => $config];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_interfaces(self):
        return self._get_config_section("interfaces")

    @_log_errors
    def get_interface(self, interface):
        return self.get_interfaces()[interface]

    @_log_errors
    def get_interface_by_description(self, interface):
        interfaces = self.get_interfaces()
        for i_interface in interfaces.keys():
            if interfaces[i_interface]["descr"] == interface:
                return interfaces[i_interface]

    @_log_errors
    def enable_filter_rule_by_tracker(self, tracker):
        config = self.get_config()
        for rule in config["filter"]["rule"]:
            if rule.get("tracker") == tracker and "disabled" in rule:
                del rule["disabled"]
                self._restore_config_section("filter", config["filter"])

    @_log_errors
    def disable_filter_rule_by_tracker(self, tracker):
        config = self.get_config()
        for rule in config["filter"]["rule"]:
            if rule.get("tracker") == tracker and "disabled" not in rule:
                rule["disabled"] = ""
                self._restore_config_section("filter", config["filter"])

    @_log_errors
    def enable_nat_port_forward_rule_by_created_time(self, created_time):
        config = self.get_config()
        if not created_time: return
        for rule in config["nat"]["rule"]:
            if dict_get(rule, "created.time") == created_time and "disabled" in rule:
                del rule["disabled"]
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def disable_nat_port_forward_rule_by_created_time(self, created_time):
        config = self.get_config()
        if not created_time: return
        for rule in config["nat"]["rule"]:
            if dict_get(rule, "created.time") == created_time and "disabled" not in rule:
                rule["disabled"] = ""
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def enable_nat_outbound_rule_by_created_time(self, created_time):
        config = self.get_config()
        if not created_time: return
        for rule in config["nat"]["outbound"]["rule"]:
            if dict_get(rule, "created.time") == created_time and "disabled" in rule:
                del rule["disabled"]
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def disable_nat_outbound_rule_by_created_time(self, created_time):
        config = self.get_config()
        if not created_time: return
        for rule in config["nat"]["outbound"]["rule"]:
            if dict_get(rule, "created.time") == created_time and "disabled" not in rule:
                rule["disabled"] = ""
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def get_configured_interface_descriptions(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$toreturn = ["data" => get_configured_interface_with_descr()];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_gateways(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$toreturn = ["data" => return_gateways_array()];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_gateway(self, gateway):
        return self.get_gateways().get(gateway)

    @_log_errors
    def get_gateways_status(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$toreturn = ["data" => return_gateways_status(true)];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_gateway_status(self, gateway):
        return self.get_gateways_status().get(gateway)

    @_log_errors
    def get_arp_table(self, resolve_hostnames=False):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"resolve_hostnames": resolve_hostnames})}', true);
$toreturn = ["data" => system_get_arp_table($data["resolve_hostnames"])];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def set_default_gateway(self, gateway, ip_version="4"):
        key = "defaultgw4" if "4" in str(ip_version) else "defaultgw6"
        script = f"""
require_once '/etc/inc/config.inc';
global $config;
$data = json_decode('{json.dumps({"key": key, "gateway": gateway})}', true);
$config['gateways'][$data["key"]] = $data["gateway"];
mark_subsystem_dirty('staticroutes');
write_config("System - Gateways: save default gateway");
$retval = 0;
$retval |= system_routing_configure();
$retval |= system_resolvconf_generate();
$retval |= filter_configure();
setup_gateways_monitor();
send_event("service reload dyndnsall");
if ($retval == 0) {{ clear_subsystem_dirty('staticroutes'); }}
$toreturn = ["data" => $retval];
"""
        self._exec_php(script)

    @_log_errors
    def get_services(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
require_once '/etc/inc/service-utils.inc';
$s = get_services();
$services = [];
foreach($s as $service) {
  if (is_array($service) && !empty($service)) { $services[] = $service; }
}
$toreturn = ["data" => $services];
"""
        response = self._exec_php(script)
        for service in response["data"]:
            if "status" not in service:
                service["status"] = self.get_service_is_running(service["name"], service)
        return response["data"]

    @_log_errors
    def get_service_is_enabled(self, service_name, service={}):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name})}', true);
$toreturn = ["data" => is_service_enabled($data["service_name"])];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_service_is_running(self, service_name, service={}):
        service = normalize_service_data(service)
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name, "service": service})}', true);
$service_name = $data["service_name"];
$service = $data["service"] ?: [];
if ($service_name == "openvpn" && $service) {{
  $service["name"] = $service["name"] ?: $service_name;
  $service["vpnmode"] = $service["vpnmode"] ?: $service["mode"];
  $service["mode"] = $service["mode"] ?: $service["vpnmode"];
  $service["id"] = $service["vpnid"];
  $toreturn = ["data" => (bool) get_service_status($service)];
}} else {{
  $toreturn = ["data" => (bool) is_service_running($service_name)];
}}
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def start_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = f"""
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name, "service": service})}', true);
$service_name = $data["service_name"];
$service = $data["service"] ?: [];
if ($service_name == "openvpn" && $service) {{
  $service["name"] = $service["name"] ?: $service_name;
  $service["vpnmode"] = $service["vpnmode"] ?: $service["mode"];
  $service["mode"] = $service["mode"] ?: $service["vpnmode"];
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}} else {{
  $is_running = is_service_running($service_name);
}}
if (!$is_running) {{ service_control_start($service_name, $service); }}
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def stop_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = f"""
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name, "service": service})}', true);
$service_name = $data["service_name"];
$service = $data["service"] ?: [];
if ($service_name == "openvpn" && $service) {{
  $service["name"] = $service["name"] ?: $service_name;
  $service["vpnmode"] = $service["vpnmode"] ?: $service["mode"];
  $service["mode"] = $service["mode"] ?: $service["vpnmode"];
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}} else {{
  $is_running = is_service_running($service_name);
}}
if ($is_running) {{ service_control_stop($service_name, $service); }}
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def restart_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = f"""
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name, "service": service})}', true);
$service_name = $data["service_name"];
$service = $data["service"] ?: [];
if ($service_name == "openvpn" && $service) {{
  $service["name"] = $service["name"] ?: $service_name;
  $service["vpnmode"] = $service["vpnmode"] ?: $service["mode"];
  $service["mode"] = $service["mode"] ?: $service["vpnmode"];
  $service["id"] = $service["vpnid"];
}}
service_control_restart($service_name, $service);
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def restart_service_if_running(self, service_name, service={}):
        service = normalize_service_data(service)
        script = f"""
require_once '/etc/inc/service-utils.inc';
$data = json_decode('{json.dumps({"service_name": service_name, "service": service})}', true);
$service_name = $data["service_name"];
$service = $data["service"] ?: [];
if ($service_name == "openvpn" && $service) {{
  $service["name"] = $service["name"] ?: $service_name;
  $service["vpnmode"] = $service["vpnmode"] ?: $service["mode"];
  $service["mode"] = $service["mode"] ?: $service["vpnmode"];
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}} else {{
  $is_running = is_service_running($service_name);
}}
if ($is_running) {{ service_control_restart($service_name, $service); }}
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def get_dhcp_leases(self, dns_lookups=None):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"dns_lookups": dns_lookups})}', true);
$toreturn = ["data" => system_get_dhcpleases($data["dns_lookups"])];
"""
        return self._exec_php(script)["data"]["lease"]

    @_log_errors
    def get_virtual_ips(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
global $config;
$vips = [];
if ($config['virtualip'] && is_iterable($config['virtualip']['vip'])) {
  foreach ($config['virtualip']['vip'] as $vip) { $vips[] = $vip; }
}
$toreturn = ["data" => $vips];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_carp_status(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$toreturn = ["data" => get_carp_status()];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_carp_interface_status(self, uniqueid):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"uniqueid": uniqueid})}', true);
$carp_if = "_vip{{$data['uniqueid']}}";
$toreturn = ["data" => get_carp_interface_status($carp_if)];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_carp_interfaces(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
global $config;
$vips = [];
if ($config['virtualip'] && is_iterable($config['virtualip']['vip'])) {
  foreach ($config['virtualip']['vip'] as $vip) {
    if ($vip["mode"] != "carp") continue;
    $vips[] = $vip;
  }
}
foreach ($vips as &$vip) {
  $vip["status"] = get_carp_interface_status("_vip{$vip['uniqid']}");
}
$toreturn = ["data" => $vips];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def delete_arp_entry(self, ip):
        if len(ip) < 1: return
        script = f"""
$data = json_decode('{json.dumps({"ip": ip})}', true);
$toreturn = ["data" => mwexec("arp -d " . trim($data["ip"]), true)];
"""
        self._exec_php(script)

    @_log_errors
    def arp_get_mac_by_ip(self, ip, do_ping=True):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"ip": ip, "do_ping": do_ping})}', true);
$toreturn = ["data" => arp_get_mac_by_ip($data["ip"], $data["do_ping"])];
"""
        response = self._exec_php(script)["data"]
        return response if response else None

    @_log_errors
    def reset_state_table(self):
        self._exec_php('mwexec("/sbin/pfctl -F states");')

    @_log_errors
    def kill_states(self, source, destination=None):
        if destination is None:
            script = f"""
$data = json_decode('{json.dumps({"source": source})}', true);
mwexec("/sbin/pfctl -k {{$data['source']}}");
"""
        else:
            script = f"""
$data = json_decode('{json.dumps({"source": source, "destination": destination})}', true);
mwexec("/sbin/pfctl -k {{$data['source']}} -k {{$data['destination']}}");
"""
        self._exec_php(script)

    @_log_errors
    def system_reboot(self, type="normal"):
        script = f"""
$data = json_decode('{json.dumps({"type": type})}', true);
$type = strtolower($data["type"]);
switch ($type) {{
    case 'fsck':
        if (php_uname('m') != 'arm') mwexec('/sbin/nextboot -e "pfsense.fsck.force=5"');
        system_reboot(); break;
    case 'reroot': system_reboot_sync(true); break;
    case 'normal': system_reboot(); break;
}}
$toreturn = ["data" => true];
"""
        try:
            self._exec_php(script)
        except ExpatError:
            pass

    @_log_errors
    def system_halt(self):
        try:
            self._exec_php('system_halt(); $toreturn = ["data" => true];')
        except ExpatError:
            pass

    @_log_errors
    def send_wol(self, interface, mac):
        script = f"""
$data = json_decode('{json.dumps({"interface": interface, "mac": mac})}', true);
$if = $data["interface"]; $mac = $data["mac"];
function send_wol($if, $mac) {{
        $ipaddr = get_interface_ip($if);
        if (!is_ipaddr($ipaddr) || !is_macaddr($mac)) return false;
        $bcip = gen_subnet_max($ipaddr, get_interface_subnet($if));
        return (bool) !mwexec("/usr/local/bin/wol -i {{$bcip}} {{$mac}}");
}}
$toreturn = ["data" => send_wol($if, $mac)];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_telemetry(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
require_once '/usr/local/www/includes/functions.inc.php';
require_once '/etc/inc/config.inc';
require_once '/etc/inc/pfsense-utils.inc';
require_once '/etc/inc/system.inc';
require_once '/etc/inc/util.inc';
require_once 'interfaces.inc';
require_once '/etc/inc/openvpn.inc';
require_once '/etc/inc/ipsec.inc';

global $config;
global $g;

function stripalpha($s) { return preg_replace("/\\D/", "", $s); }

$mbuf = null; $mbufpercent = null;
get_mbuf($mbuf, $mbufpercent);
$mbuf_parts = explode("/", $mbuf);

$filesystems = get_mounted_filesystems();
$ifdescrs = get_configured_interface_with_descr();

$boottime = exec_command("sysctl kern.boottime");
preg_match("/sec = [0-9]*/", $boottime, $matches);
$boottime = (int) trim(explode("=", $matches[0])[1]);

$pfstate = get_pfstate();
$pfstate_parts = explode("/", $pfstate);
$cpu_usage = cpu_usage();
$cpu_usage_parts = explode("|", $cpu_usage);
$system_load_average = get_load_average();
$system_load_average_parts = explode(",", $system_load_average);
$cpu_frequency = get_cpufreq();
$cpu_frequency_parts = explode(",", $cpu_frequency);

$memory_info = exec_command("sysctl hw.physmem hw.usermem hw.realmem vm.swap_total vm.swap_reserved");
$memory_parts = explode("\n", $memory_info);
$ovpn_servers = openvpn_get_active_servers();

$wan_ip = get_interface_ip("wan");
$pfb_status = false;
if (isset($config['installedpackages']['pfblockerng']['config'][0]['enable'])) {
    $pfb_status = ($config['installedpackages']['pfblockerng']['config'][0]['enable'] === 'on');
}

$toreturn = [
  "wan_ip" => $wan_ip,
  "pfblockerng" => [
      "enabled" => $pfb_status
  ],
  "pfstate" => [
    "used" => (int) $pfstate_parts[0],
    "total" => (int) $pfstate_parts[1],
    "used_percent" => get_pfstate(true),
  ],
  "mbuf" => [
    "used" => (int) $mbuf_parts[0],
    "total" => (int) $mbuf_parts[1],
    "used_percent" => floatval($mbufpercent),
  ],
  "memory" => [
    "swap_used_percent" => floatval(swap_usage()),
    "used_percent" => floatval(mem_usage()),
    "physmem" => (int) trim(explode(":", $memory_parts[0])[1]),
    "usermem" => (int) trim(explode(":", $memory_parts[1])[1]),
    "realmem" => (int) trim(explode(":", $memory_parts[2])[1]),
    "swap_total" => (int) trim(explode(":", $memory_parts[3])[1]),
    "swap_reserved" => (int) trim(explode(":", $memory_parts[4])[1]),
  ],
  "system" => [
    "boottime" => $boottime,
    "uptime" => (int) get_uptime_sec(),
    "temp" => floatval(get_temp()),
    "load_average" => [
        "one_minute" => floatval(trim($system_load_average_parts[0])),
        "five_minute" => floatval(trim($system_load_average_parts[1])),
        "fifteen_minute" => floatval(trim($system_load_average_parts[2])),
    ],
  ],
  "cpu" => [
    "frequency" => [
        "current" => (int) stripalpha($cpu_frequency_parts[0]),
        "max" => (int) stripalpha($cpu_frequency_parts[1]),
    ],
    "speed" => (int) get_cpu_speed(),
    "count" => (int) get_cpu_count(),
    "ticks" => [
        "total" => (int) $cpu_usage_parts[0],
        "idle" => (int) $cpu_usage_parts[1],
    ],
  ],
  "filesystems" => $filesystems,
  "interfaces" => [],
  "openvpn" => [],
  "ipsec" => [],
  "gateways" => return_gateways_status(true),
  "gateways_detail" => return_gateways_array(),
];

foreach ($ifdescrs as $ifdescr => $ifname) {
  $data = get_interface_info("{$ifdescr}");
  $data["descr"] = $ifname;
  $data["ifname"] = $ifdescr;
  $toreturn["interfaces"]["{$ifdescr}"] = $data;
}

foreach ($ovpn_servers as $server) {
  $vpnid = $server["vpnid"];
  $total_bytes_recv = 0; $total_bytes_sent = 0;
  foreach ($server["conns"] as $conn) {
    $total_bytes_recv += $conn["bytes_recv"];
    $total_bytes_sent += $conn["bytes_sent"];
  }
  
  $toreturn["openvpn"]["servers"][$vpnid] = [
      "name" => $server["name"],
      "vpnid" => $vpnid,
      "connected_client_count" => count($server["conns"]),
      "total_bytes_recv" => $total_bytes_recv,
      "total_bytes_sent" => $total_bytes_sent
  ];
}
"""
        data = self._exec_php(script)
        for fs in data["filesystems"]:
            fs["percent_used"] = int(fs["percent_used"])
        if isinstance(data["gateways"], list):
            data["gateways"] = {}
        return data

    @_log_errors
    def enable_pfblockerng(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey; unlock($xmlrpclockkey);
global $config;
if (isset($config['installedpackages']['pfblockerng'])) {
    $config['installedpackages']['pfblockerng']['config'][0]['enable'] = 'on';
    write_config("Home Assistant: Enabled pfBlockerNG");
    mwexec_bg("/usr/local/bin/php /usr/local/www/pfblockerng/pfblockerng.php dc >> /var/log/pfblockerng/pfblockerng.log 2>&1");
}
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def disable_pfblockerng(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey; unlock($xmlrpclockkey);
global $config;
if (isset($config['installedpackages']['pfblockerng'])) {
    $config['installedpackages']['pfblockerng']['config'][0]['enable'] = '';
    write_config("Home Assistant: Disabled pfBlockerNG");
    mwexec_bg("/usr/local/bin/php /usr/local/www/pfblockerng/pfblockerng.php dc >> /var/log/pfblockerng/pfblockerng.log 2>&1");
}
$toreturn = ["data" => true];
"""
        self._exec_php(script)

    @_log_errors
    def are_notices_pending(self, category="all"):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"category": category})}', true);
$toreturn = ["data" => are_notices_pending($data["category"])];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def get_notices(self, category="all"):
        script = f"""
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);
$data = json_decode('{json.dumps({"category": category})}', true);
$value = get_notices($data["category"]);
$toreturn = ["data" => $value ? $value : false];
"""
        value = self._exec_php(script)["data"]
        if value is False: return []
        
        notices = []
        for key in value.keys():
            notice = value.get(key)
            notice["created_at"] = key
            notices.append(notice)
        return notices

    @_log_errors
    def file_notice(self, id, notice, category="General", url="", priority=1, local_only=False):
        script = f"""
$data = json_decode('{json.dumps({"id": id, "notice": notice, "category": category, "url": url, "priority": priority, "local_only": local_only})}', true);
$toreturn = ["data" => file_notice($data["id"], $data["notice"], $data["category"], $data["url"], $data["priority"], $data["local_only"])];
"""
        return self._exec_php(script)["data"]

    @_log_errors
    def close_notice(self, id):
        script = f"""
$data = json_decode('{json.dumps({"id": id})}', true);
close_notice($data["id"]);
$toreturn = ["data" => true];
"""
        return self._exec_php(script)["data"]