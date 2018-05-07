# Functional Tests for TempestaFW

## Recommended configuration

Running tests during development process can cause crashes to TempestaFW.
Since TempestaFW is implemented as a set of kernel modules it is not convenient
to run testing framework on the same host. It is recommended to run testing
framework on a separated host.

Recommended test-beds:

- Local testing. All parts of the testing framework are running on the same
host. The simpliest configuration to check that current revision of TempestaFW
passes all the functional tests. It is default configuration.
```
    ┌─────────────────────────────────────────────┐
    │ Testing Framework + TempestaFW + Web Server │
    └─────────────────────────────────────────────┘
```

- With isolated testing framework. This preset more helpful for development
process, since testing framework itself is isolated from possible kernel
crashes or hangs. This configuration is recommended for TempestaFW developers.
```
    ┌───────────────────┐
    │ Testing Framework ├────┐
    └──────┬────────────┘    │ Management over SSH
           │              ┌──┴──────────────────────┐
           │              │ TempestaFW + Web Server │
           │              └───────────────┬─────────┘
           └──────────────────────────────┘
          Separated network for test traffic
```

- Fully distributed. 3 different hosts with their own roles are used. This
configuration isolates traffic generated by benchmark utilities and traffic
generators in test network. Handy for stress and performance testing but require
a lot of resources.
```
    ┌───────────────────┐
    │ Testing Framework ├────┐
    └──────┬────────────┘    │ Management over SSH
           │                 ├────────────────────┐
           │          ┌──────┴─────┐        ┌─────┴──────┐
           │          │ TempestaFW │        │ Web Server │
           │          └──────┬─────┘        └─────┬──────┘
           └─────────────────┴────────────────────┘
              Separated network for test traffic
```

There is two different models of tests: workload tests and pure functional
tests. Workload tests uses fully functional HTTP benchmark programs (ab,
wrk) and HTTP servers (Apache, nginx) to check TempestaFW behaviour. This type
of tests is used for schedulers, stress and performance testing.

Pure functional tests check internal logic. Here combined HTTP client-server
server is used. It sends HTTP messages to TempestaFW, analyses how they are
forwarded to server, and vice versa, which server connections are used.


## Requirements

- Host for testing framework: `Python2`, `python2-paramiko`,
`python-configparser`, `python-subprocess32`, `wrk`, `ab`, `python-scapy`
- All hosts except previous one: `sftp-server`
- Host for running TempestaFW: Linux kernel with Tempesta, TempestaFW sources,
`systemtap`, `tcpdump`
- Host for running server: `nginx`, web content directory accessible by nginx

`wrk` is an HTTP benchmarking tool, available from [Github](https://github.com/wg/wrk).

`ab` is Apache benchmark tool, that can be found in `apache2-utils` package in
Debian or `httpd-tools` in CentOS.

Unfortunately, CentOS does not have `python-subprocess32` package, but it can be
downloaded from [CentOS CBS](https://cbs.centos.org/koji/buildinfo?buildID=10904)

Testing framework manages other hosts via SSH protocol, so the host running
testing framework must be able to be authenticated on other hosts by the key.
That can be done using `ssh-copy-id`.


## Run tests

### Configuration

Testing framework is configured via `tests_config.ini` file. Example
configuration is described in `tests_config.ini.sample` file.
You can also create default tests configuration by calling:

```sh
$ ./run_tests.py -d
```

There is 4 sections in configuration: `General`, `Client`, `Tempesta`, `Server`.

#### General Section

`General` section describes the options related to testing framework itself.

`verbose`: verbose level of output:
- `0` — quiet mode, result of each test is shown by symbols. `.` — passed, `F` -
failed, `u` — unexpected success, `x` — expected failure. `s` — skipped;
- `1` — Show test names and doc strings;
- `2` — Show tests names and performance counters;
- `3` — Full debug output.

`duration` option controls duration in seconds of each workload test. Use small
values to obtain results quickly add large for more heavy stress tests. Default
is `10` seconds.

`log_file` option specifies a file to tee (duplicate) tests' stderr to.

This group of options can be overridden by command line options, for more
information run tests with `-h` key.
```sh
$ ./run_tests.py -h
```

#### Client Section

Clients are always ran locally (on the same host where the testing framework
runs). In certain tests, backend servers are also ran locally (disregarding
[server configuration](#server-section)).

`ip` — IPv4/IPv6 address of this host in the test network, as reachable from
the host running TempestaFW.

`workdir` — absolute path to a R/W directory on the host to place temporary
files in.

`ab`, `wrk` — pathes to the corresponding binaries, either absolute pathes or
names available in PATH.

#### Tempesta Section

`ip` — IPv4/IPv6 address of the TempestaFW host in test network, as reachable
from the client and server hosts. 

`hostname`, `port`, `user` — address and credentials used to reach the host via
SSH. If hostname is `localhost`, TempestaFW will be ran locally.

`workdir` — absolute path to the TempestaFW source tree.

`config` — workdir-relative or absolute path to the temporary TempestaFW config
that will be created during testing.

#### Server Section

`ip` — IPv4/IPv6 address of the backend server host in test network, as
reachable from the host running TempestaFW.

`workdir` — absolute path to a R/W directory on the host to place temporary
files in.

`nginx` — path to the corresponding binary, either absolute path or a name
available in PATH.

`resources` — absolute path to a sample web site root. Must be reachable by
nginx.


### Run tests

To run all the tests simply run:
```sh
$ ./run_tests.py
```

To run individual tests, name them in the arguments to the `run_tests.py` script
in dot-separated format (as if you were importing them as python modules,
although it is also possible to run specific testcases or even methods inside a
testcase):
```sh
$ ./run_tests.py cache.test_cache
$ ./run_tests.py cache.test_cache.TestCacheDisabled.test_cache_fullfill_all
```

To ignore specific tests, specify them in the arguments prefixed with `-`
(you may need to use `--` to avoid treating that as a flag):
```sh
$ ./run_tests.py cache -cache.test_purge # run cache.*, except cache.test_purge.*
$ ./run_tests.py -- -cache # run everything, except cache.*
```

If the testsuite was interrupted or aborted, next run will continue from the
interruption point. The resumption information is stored in the
`tests_resume.txt` file in the current working directory. It is also possible
to resume the testsuite from a specific test:
```sh
$ ./run_tests.py --resume flacky_net
$ ./run_tests.py --resume-after cache.test_purge
```

In all cases, prefix specifications are allowed, i. e. `cache.test_cache` will
match all tests in `cache/test_cache.py`, but `test_cache` will not match
anything. When resuming, execution will continue from (after) the first test
that matches the specified string.

## Adding new tests

Adding new tests is easy. First, create new Python file in the new Python module
(directory) or existing one.
Name of the file must be started with `test_`
```sh
$ mkdir my_test
$ touch my_test/test_some_feature.py
$ echo "__all__ = [ 'test_some_feature' ]" >> my_test/__init.py__
```

Import `framework.tester`: `from framework import tester`,
and derive you test class from `tester.TempestaTest`

`class Test(tester.TempestaTest)`

This class should have lists with backend
and client configuration.

`backends = [...]`
`clients = [...]`

Each config is a structure, containing item id, type, and
other options, depending on item type.

Now such backends are supported:
1) type == nginx
    status_uri: uri where nginx status is located
    config: nginx config

2) type == deproxy
    port: listen this port
    response: type of response. Now only 'static' is supported
        response == static:
            response_content: always response this content

and such clients:
1) type == wrk
    addr: 'ip:port'

2) type == deproxy
    addr: ip addr of server to connect
    port: port

All options are mandatory

nginx config, deproxy response, addr and port can use templates
in format `${part_variable}` where `part` is one of 'server',
'tempesta', 'client' or 'backend'

Example tests can be found in `selftests/test_framework.py`

Tests can be skipped or marked as expected to fail.
More info at [Python documentation](https://docs.python.org/3/library/unittest.html).

