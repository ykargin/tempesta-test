"""Tests for Frang directive `whitelist_mark`."""

from framework import curl_client, deproxy_client, tester
from framework.mixins import NetfilterMarkMixin
from helpers import remote, tempesta, tf_cfg

__author__ = "Tempesta Technologies, Inc."
__copyright__ = "Copyright (C) 2023 Tempesta Technologies, Inc."
__license__ = "GPL2"


class FrangWhitelistMarkTestCase(NetfilterMarkMixin, tester.TempestaTest):
    clients = [
        # basic request testing
        {
            "id": "deproxy-cl",
            "type": "deproxy",
            "port": "80",
            "addr": "${tempesta_ip}",
        },
        # curl client for connection_rate testing
        {
            "id": "curl-1",
            "type": "curl",
            "addr": "${tempesta_ip}:80",
            "cmd_args": "-v",
            "headers": {
                "Connection": "close",
            },
        },
    ]

    backends = [
        {
            "id": "deproxy-srv",
            "type": "deproxy",
            "port": "8000",
            "response": "static",
            "response_content": "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n",
        },
    ]

    tempesta = {
        "config": """
            listen 80;

            frang_limits {
                http_strict_host_checking false;
                http_methods GET;
                http_uri_len 20;
                tcp_connection_rate 1;
            }
            block_action attack reply;
            block_action error reply;

            whitelist_mark 1;

            srv_group sg1 {
                server ${server_ip}:8000;
            }

            vhost vh1 {
                resp_hdr_set Strict-Transport-Security "max-age=31536000; includeSubDomains";
                resp_hdr_set Content-Security-Policy "upgrade-insecure-requests";
                sticky {
                    cookie enforce name=cname;
                    js_challenge resp_code=503 delay_min=1000 delay_range=1500
                    delay_limit=100 ${tempesta_workdir}/js_challenge.html;
                }
                proxy_pass sg1;
            }

            http_chain {
                -> vh1;
            }
        """,
    }

    def prepare_js_templates(self):
        srcdir = tf_cfg.cfg.get("Tempesta", "srcdir")
        workdir = tf_cfg.cfg.get("Tempesta", "workdir")
        template = "%s/etc/js_challenge.tpl" % srcdir
        js_code = "%s/etc/js_challenge.js.tpl" % srcdir
        remote.tempesta.run_cmd("cp %s %s" % (js_code, workdir))
        remote.tempesta.run_cmd("cp %s %s/js_challenge.tpl" % (template, workdir))

    def setUp(self):
        self.prepare_js_templates()
        return super().setUp()

    def test_whitelisted_basic_request(self):
        self.start_all_services()
        self.set_nf_mark(1)

        client: deproxy_client.DeproxyClient = self.get_client("deproxy-cl")
        client.send_request(
            client.create_request(uri="/", method="GET", headers=[]),
            expected_status_code="200",
        )

    def test_whitelisted_frang_http_uri_len(self):
        self.start_all_services()
        self.set_nf_mark(1)

        client: deproxy_client.DeproxyClient = self.get_client("deproxy-cl")
        client.send_request(
            # very long uri
            client.create_request(uri="/" + "a" * 25, method="GET", headers=[]),
            expected_status_code="200",
        )

    def test_whitelisted_frang_connection_rate(self):
        self.start_all_services()
        self.set_nf_mark(1)

        connections = 5
        curl: curl_client.CurlClient = self.get_client("curl-1")
        curl.uri += f"[1-{connections}]"
        curl.parallel = connections
        curl.start()
        curl.wait_for_finish()
        curl.stop()
        # we expect all requests to receive 200
        self.assertEqual(
            curl.statuses,
            {200: connections},
            "Client is whitelisted, but connection rate is still aplied.",
        )

    def test_non_whitelisted_request_are_js_challenged(self):
        self.start_all_services()

        client: deproxy_client.DeproxyClient = self.get_client("deproxy-cl")
        client.send_request(
            client.create_request(uri="/", method="GET", headers=[]),
            expected_status_code="503",
        )
