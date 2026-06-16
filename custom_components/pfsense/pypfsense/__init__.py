"""
note that the xmlrpc api only allows a single request to be handled at a time
likely via some sort of mutex.
"""

import json
import logging
import re
import socket
import ssl
from urllib.parse import quote_plus, urlparse
from xml.parsers.expat import ExpatError
import xmlrpc.client

# value to set as the socket timeout
DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


def dict_get(data: dict, path: str, default=None):
    pathList = re.split(r"\.", path, flags=re.IGNORECASE)
    result = data
    for key in pathList:
        try:
            key = int(key) if key.isnumeric() else key
            result = result[key]
        except Exception:
            result = default
            break

    return result


def normalize_service_data(service):
    service_data_type = type(service).__name__
    if service_data_type == "dict":
        pass
    elif service_data_type == "NoneType":
        service = {}
    elif service_data_type == "str":
        if len(service) > 0:
            service = json.loads(service)
        else:
            service = {}
    else:
        raise TypeError("invalid datatype for variable `service`: " + service_data_type)

    return service


class Client(object):
    """pfSense Client"""

    def __init__(self, url, username, password, opts=None):
        """pfSense Client initializer."""

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
        if "verify_ssl" in self._opts.keys():
            verify_ssl = self._opts["verify_ssl"]

        if self._url_parts.scheme == "https" and not verify_ssl:
            context = ssl._create_unverified_context()

        verbose = False
        proxy = xmlrpc.client.ServerProxy(self._url, context=context, verbose=verbose)
        return proxy

    def _apply_timeout(func):
        def inner(*args, **kwargs):
            response = None
            default_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(DEFAULT_TIMEOUT)
                response = func(*args, **kwargs)
            finally:
                socket.setdefaulttimeout(default_timeout)
            return response

        return inner

    def _log_errors(func):
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseException as err:
                _LOGGER.error(f"Unexpected {func.__name__} error {err=}, {type(err)=}")
                raise err

        return inner

    @_apply_timeout
    def _get_config_section(self, section):
        response = self._get_proxy().pfsense.backup_config_section([section])
        return response[section]

    @_apply_timeout
    def _restore_config_section(self, section_name, data):
        params = {section_name: data}
        response = self._get_proxy().pfsense.restore_config_section(params, 60)
        return response

    @_apply_timeout
    def _exec_php(self, script):
        script = """
ini_set('display_errors', 0);

{}

$toreturn_real = $toreturn;
$toreturn = [];
$toreturn["real"] = json_encode($toreturn_real);
""".format(script)
        response = self._get_proxy().pfsense.exec_php(script)
        response = json.loads(response["real"])
        return response

    def _exec_php_no_timeout(self, script):
        script = """
ini_set('display_errors', 0);

{}

$toreturn_real = $toreturn;
$toreturn = [];
$toreturn["real"] = json_encode($toreturn_real);
""".format(script)
        response = self._get_proxy().pfsense.exec_php(script)
        response = json.loads(response["real"])
        return response

    def _exec_command(self, command, background=False):
        script = """
$data = json_decode('{}', true);
if ($data["background"]) {{
    $ret = mwexec_bg($data["command"]);    
}}
else {{
    $ret = mwexec($data["command"]);
}}

$toreturn = [
  "data" => $ret,
];
""".format(json.dumps({"command": command, "background": background}))
        response = self._exec_php(script)
        return response["data"]

    @_apply_timeout
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

$toreturn = [
  "data" => [
      "base" => get_system_pkg_version(),
      "packages" => [],
    ]
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def upgrade_firmware(self):
        script = """
$ret = mwexec_bg("pfSense-upgrade -y -l /tmp/hass-upgrade.log -p /tmp/hass-upgrade.sock");
$toreturn = [
  "data" => $ret,
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def pid_is_running(self, pid):
        script = """
$data = json_decode('{}', true);
$running = posix_kill($data["pid"],0);
$toreturn = [
  "data" => $running,
];
""".format(json.dumps({"pid": pid}))

        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_system_serial(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$toreturn = [
  "data" => system_get_serial(),
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_netgate_device_id(self):
        script = """
$toreturn = [
  "data" => system_get_uniqueid(),
];
"""
        response = self._exec_php(script)
        return response["data"]

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
        response = self._exec_php(script)
        return response

    @_log_errors
    def get_config(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

global $config;

$toreturn = [
  "data" => $config,
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_interfaces(self):
        return self._get_config_section("interfaces")

    @_log_errors
    def get_interface(self, interface):
        interfaces = self.get_interfaces()
        return interfaces[interface]

    @_log_errors
    def get_interface_by_description(self, interface):
        interfaces = self.get_interfaces()
        for i, i_interface in enumerate(interfaces.keys()):
            if interfaces[i_interface]["descr"] == interface:
                return interfaces[i_interface]

    @_log_errors
    def enable_filter_rule_by_tracker(self, tracker):
        config = self.get_config()
        for rule in config["filter"]["rule"]:
            if "tracker" not in rule.keys():
                continue
            if rule["tracker"] != tracker:
                continue

            if "disabled" in rule.keys():
                del rule["disabled"]
                self._restore_config_section("filter", config["filter"])

    @_log_errors
    def disable_filter_rule_by_tracker(self, tracker):
        config = self.get_config()
        for rule in config["filter"]["rule"]:
            if "tracker" not in rule.keys():
                continue
            if rule["tracker"] != tracker:
                continue

            if "disabled" not in rule.keys():
                rule["disabled"] = ""
                self._restore_config_section("filter", config["filter"])

    @_log_errors
    def enable_nat_port_forward_rule_by_created_time(self, created_time):
        config = self.get_config()
        if created_time is None:
            return

        for rule in config["nat"]["rule"]:
            if dict_get(rule, "created.time") != created_time:
                continue

            if "disabled" in rule.keys():
                del rule["disabled"]
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def disable_nat_port_forward_rule_by_created_time(self, created_time):
        config = self.get_config()
        if created_time is None:
            return

        for rule in config["nat"]["rule"]:
            if dict_get(rule, "created.time") != created_time:
                continue

            if "disabled" not in rule.keys():
                rule["disabled"] = ""
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def enable_nat_outbound_rule_by_created_time(self, created_time):
        config = self.get_config()
        if created_time is None:
            return

        for rule in config["nat"]["outbound"]["rule"]:
            if dict_get(rule, "created.time") != created_time:
                continue

            if "disabled" in rule.keys():
                del rule["disabled"]
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def disable_nat_outbound_rule_by_created_time(self, created_time):
        config = self.get_config()
        if created_time is None:
            return

        for rule in config["nat"]["outbound"]["rule"]:
            if dict_get(rule, "created.time") != created_time:
                continue

            if "disabled" not in rule.keys():
                rule["disabled"] = ""
                self._restore_config_section("nat", config["nat"])

    @_log_errors
    def get_configured_interface_descriptions(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$toreturn = [
  "data" => get_configured_interface_with_descr(),
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_gateways(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$toreturn = [
  "data" => return_gateways_array(),
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_gateway(self, gateway):
        gateways = self.get_gateways()
        for g in gateways.keys():
            if g == gateway:
                return gateways[g]

    @_log_errors
    def get_gateways_status(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$toreturn = [
  "data" => return_gateways_status(true),
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_gateway_status(self, gateway):
        gateways = self.get_gateways_status()
        for g in gateways.keys():
            if g == gateway:
                return gateways[g]

    @_log_errors
    def get_arp_table(self, resolve_hostnames=False):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);
$resolve_hostnames = $data["resolve_hostnames"];
$toreturn = [
  "data" => system_get_arp_table($resolve_hostnames),
];
""".format(json.dumps({"resolve_hostnames": resolve_hostnames}))
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def set_default_gateway(self, gateway, ip_version="4"):
        ipVersion = str(ip_version)
        key = "defaultgw4"
        if "4" in ipVersion:
            key = "defaultgw4"
        if "6" in ipVersion:
            key = "defaultgw6"

        script = """
require_once '/etc/inc/config.inc';
global $config;

$data = json_decode('{}', true);
$key = $data["key"];
$config['gateways'][$key] = $data["gateway"];

mark_subsystem_dirty('staticroutes');
write_config("System - Gateways: save default gateway");

$retval = 0;
                    
$retval |= system_routing_configure();
$retval |= system_resolvconf_generate();
$retval |= filter_configure();
setup_gateways_monitor();
send_event("service reload dyndnsall");

if ($retval == 0) {{
  clear_subsystem_dirty('staticroutes');
}}

$toreturn = [
  "data" => $retval
];
""".format(json.dumps({"key": key, "gateway": gateway}))

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
  if (!is_array($service)) {
      continue;
  }
  if (!empty($service)) {
    $services[] = $service;
  }
}

$toreturn = [
  "data" => $services,
];
"""
        response = self._exec_php(script)

        for service in response["data"]:
            if "status" not in service:
                service["status"] = self.get_service_is_running(
                    service["name"], service
                )

        return response["data"]

    @_log_errors
    def get_service_is_enabled(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$toreturn = [
  "data" => is_service_enabled($service_name),
];
""".format(json.dumps({"service_name": service_name, "service": service}))
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_service_is_running(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$service = $data["service"];
if (!$service) {{
  $service = [];
}}

if ($service_name == "openvpn" && $service) {{
  if (!$service["name"]) {{
    $service["name"] = $service_name;
  }}
  if (!$service["vpnmode"] && $service["mode"]) {{
    $service["vpnmode"] = $service["mode"];
  }}
  if (!$service["mode"] && $service["vpnmode"]) {{
    $service["mode"] = $service["vpnmode"];
  }}
  $service["id"] = $service["vpnid"];
  $toreturn = [
    "data" => (bool) get_service_status($service),
  ];
}}
else {{
  $toreturn = [
    "data" => (bool) is_service_running($service_name),
  ];
}}

""".format(json.dumps({"service_name": service_name, "service": service}))
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def start_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$service = $data["service"];
if (!$service) {{
  $service = [];
}}

if ($service_name == "openvpn" && $service) {{
  if (!$service["name"]) {{
    $service["name"] = $service_name;
  }}
  if (!$service["vpnmode"] && $service["mode"]) {{
    $service["vpnmode"] = $service["mode"];
  }}
  if (!$service["mode"] && $service["vpnmode"]) {{
    $service["mode"] = $service["vpnmode"];
  }}
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}}
else {{
  $is_running = is_service_running($service_name);
}}

if (!$is_running) {{
  service_control_start($service_name, $service);
}}

$toreturn = [
  "data" => true,
];
""".format(json.dumps({"service_name": service_name, "service": service}))
        self._exec_php(script)

    @_log_errors
    def stop_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$service = $data["service"];
if (!$service) {{
  $service = [];
}}

if ($service_name == "openvpn" && $service) {{
  if (!$service["name"]) {{
    $service["name"] = $service_name;
  }}
  if (!$service["vpnmode"] && $service["mode"]) {{
    $service["vpnmode"] = $service["mode"];
  }}
  if (!$service["mode"] && $service["vpnmode"]) {{
    $service["mode"] = $service["vpnmode"];
  }}
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}}
else {{
  $is_running = is_service_running($service_name);
}}

if ($is_running) {{
  service_control_stop($service_name, $service);
}}
$toreturn = [
  "data" => true,
];
""".format(json.dumps({"service_name": service_name, "service": service}))
        self._exec_php(script)

    @_log_errors
    def restart_service(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$service = $data["service"];
if (!$service) {{
  $service = [];
}}

if ($service_name == "openvpn" && $service) {{
  if (!$service["name"]) {{
    $service["name"] = $service_name;
  }}
  if (!$service["vpnmode"] && $service["mode"]) {{
    $service["vpnmode"] = $service["mode"];
  }}
  if (!$service["mode"] && $service["vpnmode"]) {{
    $service["mode"] = $service["vpnmode"];
  }}
  $service["id"] = $service["vpnid"];
}}

service_control_restart($service_name, $service);
$toreturn = [
  "data" => true,
];
""".format(json.dumps({"service_name": service_name, "service": service}))
        self._exec_php(script)

    @_log_errors
    def restart_service_if_running(self, service_name, service={}):
        service = normalize_service_data(service)
        script = """
require_once '/etc/inc/service-utils.inc';

$data = json_decode('{}', true);
$service_name = $data["service_name"];
$service = $data["service"];
if (!$service) {{
  $service = [];
}}

if ($service_name == "openvpn" && $service) {{
  if (!$service["name"]) {{
    $service["name"] = $service_name;
  }}
  if (!$service["vpnmode"] && $service["mode"]) {{
    $service["vpnmode"] = $service["mode"];
  }}
  if (!$service["mode"] && $service["vpnmode"]) {{
    $service["mode"] = $service["vpnmode"];
  }}
  $service["id"] = $service["vpnid"];
  $is_running = (bool) get_service_status($service);
}}
else {{
  $is_running = is_service_running($service_name);
}}

if ($is_running) {{
  service_control_restart($service_name, $service);
}}
$toreturn = [
  "data" => true,
];
""".format(json.dumps({"service_name": service_name, "service": service}))
        self._exec_php(script)

    @_log_errors
    def get_dhcp_leases(self, dns_lookups=None):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);

$dns_lookups = null;
if ($data["dns_lookups"] === true || $data["dns_lookups"] === false) {{
  $dns_lookups = $data["dns_lookups"];
}}

$toreturn = [
  "data" => system_get_dhcpleases($dns_lookups),
];
""".format(json.dumps({"dns_lookups": dns_lookups}))
        response = self._exec_php(script)
        return response["data"]["lease"]

    @_log_errors
    def get_virtual_ips(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

global $config;

$vips = [];
if ($config['virtualip'] && is_iterable($config['virtualip']['vip'])) {
  foreach ($config['virtualip']['vip'] as $vip) {
    $vips[] = $vip;
  }
}

$toreturn = [
  "data" => $vips,
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_carp_status(self):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$toreturn = [
  "data" => get_carp_status(),
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_carp_interface_status(self, uniqueid):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);
$uniqueid = $data["uniqueid"];
$carp_if = "_vip{{$uniqueid}}";
$status = get_carp_interface_status($carp_if);
$toreturn = [
  "data" => $status,
];
""".format(json.dumps({"uniqueid": uniqueid}))
        response = self._exec_php(script)
        return response["data"]

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
    if ($vip["mode"] != "carp") {
      continue;
    }
    $vips[] = $vip;
  }
}

foreach ($vips as &$vip) {
  $status = get_carp_interface_status("_vip{$vip['uniqid']}");
  $vip["status"] = $status;
}

$toreturn = [
  "data" => $vips,
];
"""
        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def delete_arp_entry(self, ip):
        if len(ip) < 1:
            return
        script = """
$data = json_decode('{}', true);
$ip = trim($data["ip"]);
$ret = mwexec("arp -d " . $ip, true);
$toreturn = [
  "data" => $ret,
];
""".format(json.dumps({"ip": ip}))
        self._exec_php(script)

    @_log_errors
    def arp_get_mac_by_ip(self, ip, do_ping=True):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);
$ip = $data["ip"];
$do_ping = $data["do_ping"];
$toreturn = [
  "data" => arp_get_mac_by_ip($ip, $do_ping),
];
""".format(json.dumps({"ip": ip, "do_ping": do_ping}))
        response = self._exec_php(script)["data"]
        if not response:
            return None
        return response

    @_log_errors
    def reset_state_table(self):
        script = """
mwexec("/sbin/pfctl -F states");
"""
        self._exec_php(script)

    @_log_errors
    def kill_states(self, source, destination=None):
        if destination is None:
            script = """
$data = json_decode('{}', true);
$source = $data["source"];
mwexec("/sbin/pfctl -k $source");
""".format(json.dumps({"source": source}))
            self._exec_php(script)
            return None
        else:
            script = """
$data = json_decode('{}', true);
$source = $data["source"];
$destination = $data["destination"];
mwexec("/sbin/pfctl -k $source -k $destination");
""".format(json.dumps({"source": source, "destination": destination}))
            self._exec_php(script)
            return None

    @_log_errors
    def system_reboot(self, type="normal"):
        script = """
$data = json_decode('{}', true);
$type = $data["type"];
$type = strtolower($type);

switch ($type) {{
    case 'fsck':
        if (php_uname('m') != 'arm') {{
            mwexec('/sbin/nextboot -e "pfsense.fsck.force=5"');
        }}
        system_reboot();
        break;
    case 'reroot':
        system_reboot_sync(true);
        break;
    case 'normal':
        system_reboot();
        break;
    default:
        break;
}}

$toreturn = [
  "data" => true,
];
""".format(json.dumps({"type": type}))
        try:
            self._exec_php(script)
        except ExpatError:
            pass

    @_log_errors
    def system_halt(self):
        script = """
system_halt();
$toreturn = [
  "data" => true,
];
"""
        try:
            self._exec_php(script)
        except ExpatError:
            pass

    @_log_errors
    def send_wol(self, interface, mac):
        script = """
$data = json_decode('{}', true);
$if = $data["interface"];
$mac = $data["mac"];
function send_wol($if, $mac) {{
        $ipaddr = get_interface_ip($if);
        if (!is_ipaddr($ipaddr) || !is_macaddr($mac)) {{
                return false;
        }}

        $bcip = gen_subnet_max($ipaddr, get_interface_subnet($if));
        return (bool) !mwexec("/usr/local/bin/wol -i {{$bcip}} {{$mac}}");
}}

$value = send_wol($if, $mac);
$toreturn = [
  "data" => $value,
];
""".format(json.dumps({"interface": interface, "mac": mac}))

        response = self._exec_php(script)
        return response["data"]

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

function stripalpha($s) {
  return preg_replace("/\\\\D/", "", $s);
}

$mbuf = null;
$mbufpercent = null;
get_mbuf($mbuf, $mbufpercent);
$mbuf_parts = explode("/", $mbuf);

$filesystems = get_mounted_filesystems();
$ifdescrs = get_configured_interface_with_descr();

$boottime = exec_command("sysctl kern.boottime");
preg_match("/sec = [0-9]*/", $boottime, $matches);
$boottime = $matches[0];
$boottime = explode("=", $boottime)[1];
$boottime = (int) trim($boottime);

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

$wan_interface_key = 'wan';
foreach ($config['interfaces'] as $ifk => $ifv) {
    if ($ifk == 'wan') {
        $wan_interface_key = $ifk;
        break;
    }
}
$wan_ip_address = get_interface_ip($wan_interface_key);

$dnsbl_blocks = 0;
$ip_blocks = 0;
if (file_exists('/var/log/pfblockerng/dnsbl.log')) {
    $dnsbl_blocks = (int)exec_command("wc -l < /var/log/pfblockerng/dnsbl.log");
}
if (file_exists('/var/log/pfblockerng/ip_block.log')) {
    $ip_blocks = (int)exec_command("wc -l < /var/log/pfblockerng/ip_block.log");
}

$toreturn = [
  "wan_ip" => $wan_ip_address ? $wan_ip_address : "Disconnected",
  
  "pfblockerng" => [
    "dnsbl_blocks" => $dnsbl_blocks,
    "ip_blocks" => $ip_blocks,
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
  $data = get_interface_info("${ifdescr}");
  $data["descr"] = $ifname;
  $data["ifname"] = $ifdescr;
  $toreturn["interfaces"]["${ifdescr}"] = $data;
}

foreach ($ovpn_servers as $server) {
  $vpnid = $server["vpnid"];
  $name = $server["name"];
  $conn_count = count($server["conns"]);

  $total_bytes_recv = 0;
  $total_bytes_sent = 0;
  foreach ($server["conns"] as $conn) {
    $total_bytes_recv += $conn["bytes_recv"];
    $total_bytes_sent += $conn["bytes_sent"];
  }
  
  $toreturn["openvpn"]["servers"][$vpnid]["name"] = $name;
  $toreturn["openvpn"]["servers"][$vpnid]["vpnid"] = $vpnid;
  $toreturn["openvpn"]["servers"][$vpnid]["connected_client_count"] = $conn_count;
  $toreturn["openvpn"]["servers"][$vpnid]["total_bytes_recv"] = $total_bytes_recv;
  $toreturn["openvpn"]["servers"][$vpnid]["total_bytes_sent"] = $total_bytes_sent;
}
"""
        data = self._exec_php(script)

        for fs in data["filesystems"]:
            fs["percent_used"] = int(fs["percent_used"])

        if isinstance(data["gateways"], list):
            data["gateways"] = {}

        return data

    @_log_errors
    def update_alias_address(
        self,
        alias_name: str,
        address: str,
        action: str = "add",
        kill_states: bool = True,
    ):
        """Dynamically add or remove an IP/Host from a pfSense alias group, reload filters, and terminate target state sessions."""
        script = """
        require_once('/etc/inc/util.inc');
        require_once('/etc/inc/config.inc');
        require_once('/etc/inc/filter.inc');

        $data = json_decode('{}', true);
        $alias_name = $data["alias_name"];
        $address = trim($data["address"]);
        $action = $data["action"];
        $kill_states = (bool)$data["kill_states"];

        global $config;
        if (!is_array($config['aliases']['alias'])) {{
            $config['aliases']['alias'] = [];
        }}

        // Safely normalize single-item vs multi-item array nesting quirks
        if (count($config['aliases']['alias']) > 0 && !isset($config['aliases']['alias'][0])) {{
            $config['aliases']['alias'] = array($config['aliases']['alias']);
        }}

        $found_idx = -1;
        foreach ($config['aliases']['alias'] as $idx => $alias) {{
            if ($alias['name'] == $alias_name) {{
                $found_idx = $idx;
                break;
            }}
        }}

        if ($found_idx == -1 && $action == 'add') {{
            $new_alias = [
                'name' => $alias_name,
                'type' => 'host',
                'address' => $address,
                'descr' => 'Managed automatically by Home Assistant',
                'detail' => 'Added via HASS'
            ];
            $config['aliases']['alias'][] = $new_alias;
        }} elseif ($found_idx != -1) {{
            $addresses = array_filter(explode(' ', $config['aliases']['alias'][$found_idx]['address']));
            $details = array_filter(explode('||', $config['aliases']['alias'][$found_idx]['detail']));
            
            $key = array_search($address, $addresses);
            
            if ($action == 'add' && $key === false) {{
                $addresses[] = $address;
                $details[] = 'Added via HASS';
            }} elseif ($action == 'remove' && $key !== false) {{
                unset($addresses[$key]);
                unset($details[$key]);
            }}
            
            $config['aliases']['alias'][$found_idx]['address'] = implode(' ', $addresses);
            $config['aliases']['alias'][$found_idx]['detail'] = implode('||', $details);
        }}

        write_config("Modified alias " . $alias_name . " via Home Assistant");
        filter_configure();

        // Target and kill the states so the device drops immediately
        if ($kill_states && !empty($address)) {{
            mwexec("/sbin/pfctl -k " . escapeshellarg($address));
            mwexec("/sbin/pfctl -k 0.0.0.0/0 -k " . escapeshellarg($address));
        }}

        $toreturn = ["data" => true];
        """.format(
            json.dumps(
                {
                    "alias_name": alias_name,
                    "address": address,
                    "action": action,
                    "kill_states": kill_states,
                }
            )
        )

        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def are_notices_pending(self, category="all"):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);
$category = $data["category"];
$toreturn = [
  "data" => are_notices_pending($category),
];
""".format(json.dumps({"category": category}))

        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def get_notices(self, category="all"):
        script = """
require_once '/etc/inc/util.inc';
global $xmlrpclockkey;
unlock($xmlrpclockkey);

$data = json_decode('{}', true);
$category = $data["category"];
$value = get_notices($category);
if (!$value) {{
    $value = false;
}}
$toreturn = [
  "data" => $value,
];
""".format(json.dumps({"category": category}))

        response = self._exec_php(script)
        value = response["data"]
        if value is False:
            return []

        notices = []
        for key in value.keys():
            notice = value.get(key)
            notice["created_at"] = key
            notices.append(notice)

        return notices

    @_log_errors
    def file_notice(
        self, id, notice, category="General", url="", priority=1, local_only=False
    ):
        script = """
$data = json_decode('{}', true);
$id = $data["id"];
$notice = $data["notice"];
$category = $data["category"];
$url = $data["url"];
$priority = $data["priority"];
$local_only = $data["local_only"];

$value = file_notice($id, $notice, $category, $url, $priority, $local_only);
$toreturn = [
  "data" => $value,
];
""".format(
            json.dumps(
                {
                    "id": id,
                    "notice": notice,
                    "category": category,
                    "url": url,
                    "priority": priority,
                    "local_only": local_only,
                }
            )
        )

        response = self._exec_php(script)
        return response["data"]

    @_log_errors
    def close_notice(self, id):
        script = """
$data = json_decode('{}', true);
$id = $data["id"];
close_notice($id);
$toreturn = [
  "data" => true,
];
""".format(json.dumps({"id": id}))

        response = self._exec_php(script)
        return response["data"]
