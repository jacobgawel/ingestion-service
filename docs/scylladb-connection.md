# ScyllaDB Connection from Host to Docker

## The Problem

When running the FastAPI application on the host and ScyllaDB inside Docker, the app fails to connect with:

```
cassandra.cluster.NoHostAvailable: ('Unable to connect to any servers', ['172.18.0.4'])
```

The IP in the error (`172.18.0.4`) is the container's internal Docker network address, not `localhost` — even though `SCYLLA_HOSTS` defaults to `localhost`.

## Why It Happens

The `cassandra-driver` (which `scylla-driver` is based on) performs **peer discovery** after the initial connection:

1. The driver connects to `localhost:9042` via Docker's port mapping. This succeeds.
2. The driver queries the node for its advertised address (`rpc_address` from `system.local`).
3. ScyllaDB reports its Docker-internal IP (e.g. `172.18.0.4`) as the `rpc_address`.
4. The driver replaces `localhost` with `172.18.0.4` in its connection pool.
5. All subsequent queries fail because `172.18.0.4` is not routable from the host.

This is standard Cassandra/Scylla driver behavior and affects any setup where the client is outside the container network.

## The Fix

Add `--broadcast-rpc-address 127.0.0.1` to the ScyllaDB container command in `docker-compose.yml`:

```yaml
scylladb:
  image: scylladb/scylla:latest
  container_name: nexus-scylladb
  ports:
    - "9042:9042"
    - "9160:9160"
  command: --smp 1 --memory 750M --overprovisioned 1 --broadcast-rpc-address 127.0.0.1
```

This tells ScyllaDB to advertise `127.0.0.1` as its client-facing address. When the driver performs peer discovery, it gets `127.0.0.1` instead of the container IP, which correctly resolves through Docker's port mapping.

After changing this, recreate the container:

```bash
docker compose up -d scylladb
```

## Verifying the Connection

Once ScyllaDB is healthy, start the app and hit the `/data/tables` endpoint:

```bash
# Check ScyllaDB is ready
docker compose exec scylladb cqlsh -e "SELECT now() FROM system.local"

# Start the app
uv run ./main.py

# Test the connection (returns tables in the configured keyspace)
curl http://localhost:8065/data/tables
```

## Notes

- This only applies when running the app **on the host**. If the app runs inside the same Docker network, it can reach ScyllaDB by container name (`scylladb:9042`) and peer discovery works normally.
- For multi-node ScyllaDB clusters in Docker, each node needs its own `--broadcast-rpc-address` set to a host-routable address.
