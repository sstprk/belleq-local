# Installing the four Mac mini lab

This guide installs the real retrieval system. It is separate from the simulator,
which needs only one computer and no external services. The reference hardware is
four Apple M2 Mac minis with 8 GB unified memory each. Use macOS 14 or newer and
Python 3.12. Measurements were made on the original lab, not on every supported OS.

## 1 Cable the isolated network

Connect each mini and the management MacBook to normal Ethernet switch ports.
The switch console/CLI port is for switch administration, not computer data.
No router or switch configuration is necessary when all ports are in the same
untagged LAN. Do not connect this switch to the campus network for the isolated run.

Configure Ethernet manually in System Settings → Network → Ethernet → Details
→ TCP/IP. Choose **Manually**, not **Using DHCP with manual address**.

| Device | IPv4 | Mask | Ethernet router and DNS |
|---|---|---|---|
| MacBook | 192.168.50.10 | 255.255.255.0 | blank |
| mini-1 | 192.168.50.11 | 255.255.255.0 | blank |
| mini-2 | 192.168.50.12 | 255.255.255.0 | blank |
| mini-3 | 192.168.50.13 | 255.255.255.0 | blank |
| mini-4 | 192.168.50.14 | 255.255.255.0 | blank |

Use a subnet that does not overlap the installation Wi-Fi network. A self-assigned
169.254 address is not a fixed-address plan. Record each Ethernet link's negotiated
speed; a MacBook's USB adapter speed does not prove the mini-to-mini link speed.

```bash
networksetup -listallhardwareports
networksetup -listallnetworkservices
networksetup -getinfo 'Ethernet'
route -n get 192.168.50.12
# Replace en0 with the interface returned by the route command.
ifconfig en0
ping -c 3 192.168.50.12
```

The Ethernet service may have another name. Never copy an interface identifier
without checking it. If ping stops after assigning an address, check the subnet
mask, actual interface and duplicate addresses before changing SSH settings.

## 2 Enable SSH and manage from the MacBook

On each mini enable System Settings → General → Sharing → **Remote Login**, and
allow the intended local account. Remote Management is a different setting.

```bash
ssh LABUSER@192.168.50.11
ssh LABUSER@192.168.50.12
ssh LABUSER@192.168.50.13
ssh LABUSER@192.168.50.14
```

Replace `LABUSER` with the account on that machine. Verify host fingerprints on
first connection. Prefer SSH keys with `ssh-copy-id` or normal authorized-key
setup; passwords and private keys are not part of the repository. A timeout means
network/firewall/routing trouble; connection refused usually means SSH is disabled.

## 3 Install Python and a container runtime

On every mini, with internet available for installation:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
brew install python@3.12 uv colima docker docker-compose
colima start --cpu 2 --memory 2 --disk 20
docker context show
docker version
docker-compose version
```

Colima's 2 GB VM is a starting budget on an 8 GB machine, not a measured optimum.
Do not run Colima and Docker Desktop simultaneously. Docker Desktop is also an
option; its Compose command is usually `docker compose` instead of `docker-compose`.
If Homebrew reports that Compose is not discovered as a plugin, the standalone
`docker-compose` command above avoids editing the global Docker configuration.

If Homebrew Python is broken, use `uv python install 3.12` and pass that interpreter
to `uv sync`. If the user's uv directories are not writable, choose writable
`UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR`; do not create the environment as root.
CMake is not required by this HTTP retrieval service itself.

## 4 Install Ollama natively

Install the [official macOS app](https://docs.ollama.com/macos), open it, then check:

```bash
ollama --version
curl --fail http://127.0.0.1:11434/api/tags
ollama pull nomic-embed-text:latest
```

On **mini-1 only**, also download the answer model:

```bash
ollama pull qwen3:1.7b
```

Every mini, including the coordinator's local retrieval service, needs the embedding
model. Ollama runs on macOS to use Apple Silicon; do not place it inside the Qdrant
Linux VM. Keep Ollama on loopback. Save `ollama --version` and `/api/tags` for every
run. Mutable tags are insufficient for exact model identity: copy the embedding
`digest` from `/api/tags` into every config's `embedding_digest` and use identical
digests on all workers. Empty digest is allowed initially and is learned at startup.
The archived preflight's exact model digests and embedding signatures are retained
in `provenance/model_fingerprints.json`. A mutable registry tag may no longer name
those same weights; check the digest rather than assuming a fresh pull reproduces
the historical embedding model.

The service uses 768-dimensional cosine vectors, `search_query: ` and
`search_document: ` prefixes, and the archived chunking schema. It checks model
dimensions and persists the schema fingerprint alongside the Qdrant collection.
Changing the model/prefix/schema requires a new collection and re-ingestion.

## 5 Check out one version on every mini

```bash
git clone https://github.com/sstprk/belleq-local.git
cd belleq-local
git checkout v0.2.0
uv sync --frozen --no-dev --python /opt/homebrew/bin/python3.12
# Select this machine's ID, mini-1 through mini-4.
cp config/categorical/mini-2.json config/local.json
docker-compose up -d
curl --fail http://127.0.0.1:6333/collections
.venv/bin/python -m belleq_lab
```

`compose.yaml` pins Qdrant v1.13.3 and exposes it only on `127.0.0.1:6333`. The API
binds to the Ethernet address in `config/local.json`, not automatically to all
interfaces. A bind error means the selected address is not assigned or the port
is occupied; stop the earlier process or choose the correct machine config.

Start workers first, then the coordinator. Leave these foreground terminals open
for initial validation. From a separate terminal on the MacBook:

```bash
curl --fail http://192.168.50.11:8000/health/ready
curl --fail http://192.168.50.12:8000/health/ready
curl --fail http://192.168.50.13:8000/health/ready
curl --fail http://192.168.50.14:8000/health/ready
```

Readiness initializes/checks dependencies; it is not a throughput benchmark.
The categorical profile preserves the archived worker descriptions covering all
12 titles, characters and topics; these are recorded in `provenance/routing_catalogue.json`.
The original three-book starter templates remain in `config/mini-N.json`.
The examples use a fresh collection name and are deployment recipes, not recovered
copies of every original machine's complete private configuration.

## 6 Persist the process and its data

After a foreground run succeeds, stop it with Ctrl+C, then on each mini:

```bash
.venv/bin/python scripts/service.py install
.venv/bin/python scripts/service.py status
tail -f logs/service.err.log
```

This installs a user LaunchAgent, independent of the SSH connection. The local user
must be logged in. It is not a system daemon that guarantees service before login.
After reboot, start Ollama and Colima/Docker, then confirm readiness. Startup failures
retry at a throttled interval. Manage it with:

```bash
.venv/bin/python scripts/service.py stop
.venv/bin/python scripts/service.py start
# To remove only the service registration:
.venv/bin/python scripts/service.py uninstall
```

Qdrant collections persist in `qdrant_data` and `qdrant_snapshots` Docker named
volumes. `docker-compose stop` preserves them. **Do not use `down -v` for ordinary
shutdown:** it removes volumes. Deleting the Colima VM can also remove its volumes.
Back up Qdrant snapshots and archive run logs before changing the setup.

## 7 Optional shared API key

For a trusted isolated LAN, templates have no key. To enable a key, set the same
`BELLEQ_API_KEY` environment variable on all APIs and evaluation clients, and send
`X-API-Key` with API calls. Export it before installing the LaunchAgent so that the
generated user plist includes it with restrictive permissions. Never commit it.
The service does not implement TLS; see [security](../SECURITY.md).

## 8 Prepare for disconnected measurements

Before removing internet access on **every mini**:

1. Finish dependency installation, `docker-compose pull`, and both required model
   pulls. Start all containers/APIs and issue one non-measured health/query request.
2. Record Git commit, Python version, package lock, OS, hardware, Ollama version,
   model digests, Qdrant image ID, collection counts and Ethernet link speeds.
3. Identify the Wi-Fi hardware port with `networksetup -listallhardwareports`.
   Disable Wi-Fi on each mini with System Settings or
   `networksetup -setairportpower WIFI_INTERFACE off` (replace the placeholder).
4. Ensure the lab switch has no internet uplink, VPN route, Internet Sharing or
   second interface that bypasses the isolation. Verify the route to every worker
   still uses Ethernet. The MacBook may retain its own internet for management;
   it must not bridge internet to the mini LAN.
5. Start the evaluator on mini-1 and capture the same host's Ethernet interface.
   No downloads or package installation should happen during measured queries.

Running already installed services needs no internet. Reinstalling from scratch
offline additionally needs platform-matching Python wheels, a saved Docker image
and the original Ollama model store. To prepare Python wheels use
`uv export --frozen --no-dev --format requirements-txt` and `pip download` before
disconnecting. Save the image with `docker image save`; restore it with
`docker image load`. Do not assume a copied `.venv` is portable.

## 9 Shutdown

Stop the evaluator, interrupt tcpdump with Ctrl+C and record the capture/drop
counts. Archive the complete run directory. Stop the user API service and then
`docker-compose stop` (and `colima stop` if used). Shut down through macOS after
writes complete. Do not delete partially written evidence to make a run look
complete; mark it interrupted and start a new uniquely named run.
