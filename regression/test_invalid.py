"""Regression tests for invalid requests and responses."""

__author__ = "Tempesta Technologies, Inc."
__copyright__ = "Copyright (C) 2017 Tempesta Technologies, Inc."
__license__ = "GPL2"


from testers import functional
from helpers import chains, deproxy, tempesta


class InvalidResponseServer(deproxy.Server):

    def __stop_server(self):
        super().__stop_server(self)
        assert len(self.connections) <= self.conns_n, \
                ('Too many connections, expect %d, got %d'
                 % (self.conns_n, len(self.connections)))

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, _ = pair
            handler = deproxy.ServerConnection(self.tester, server=self,
                                               sock=sock,
                                               keep_alive=self.keep_alive)
            self.connections.append(handler)


class TesterInvalidResponse(deproxy.Deproxy):
    def received_response(self, response):
        """Client received response for its request."""
        self.received_chain.response = response


class TestInvalidResponse(functional.FunctionalTest):

    config = "cache 0;\n"

    def assert_tempesta(self):
        """Assert that tempesta had no errors during test."""
        msg = "Tempesta have errors in processing HTTP %s."
        self.assertEqual(self.tempesta.stats.cl_msg_parsing_errors, 0, msg=(msg % "requests"))
        self.assertEqual(self.tempesta.stats.srv_msg_parsing_errors, 1, msg=(msg % "responses"))
        if not self.tfw_clnt_msg_otherr:
            self.assertEqual(self.tempesta.stats.cl_msg_other_errors, 0, msg=(msg % "requests"))
        self.assertEqual(self.tempesta.stats.srv_msg_other_errors, 0, msg=(msg % "responses"))

    def create_tester(self):
        self.tester = TesterInvalidResponse(self.client, self.servers)

    def create_servers(self):
        port = tempesta.upstream_port_start_from()
        srv = InvalidResponseServer(port=port)
        self.servers = [srv]

    def test_204_with_body(self):
        chain = chains.proxy()
        chain.server_response.status = "204"
        chain.server_response.build_message()
        chain.response = chains.make_502_expected()
        self.generic_test_routine(self.config, [chain])

    def test_no_crlf_before_body(self):
        chain = chains.proxy()
        chain.server_response.msg = chain.server_response.msg.replace("\r\n\r\n", "\r\n", 1)
        chain.response = chains.make_502_expected()
        self.generic_test_routine(self.config, [chain])
