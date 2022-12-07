# Heroku metrics collector for crates.io

This repository contains the source code of the container used to gather
crates.io's metrics.

The collector is maintained by the Rust Infrastructure team for internal use
only. While it's open source and you're free to deploy or modify it according
to its license, the team **does not provide support and will not maintain it**
for any purpose we don't need ourselves.

The contents of the repository are dual-licensed under both the
[MIT](./LICENSE-MIT) and [Apache-2.0](./LICENSE-APACHE) licenses.

## Building and running

You can build the Docker container by cloning the repository and running:

```
docker build -t crates-io-heroku-metrics .
```

Once the image is built you can run it by running:

```
docker run --rm \
    -e PASSWORD_DRAIN=${PASSWORD_DRAIN} \
    -e PASSWORD_METRICS=${PASSWORD_METRICS} \
    -p 80:80 \
    crates-io-heroku-metrics
```

The service will be bound on port 80 and protected with the `${PASSWORD_DRAIN}`
and `${PASSWORD_METRICS}` passwords. You can then configure Heroku to forward
all application logs to it:

```
heroku drains:add -a ${APP} https://drain:${PASSWORD_DRAIN}@crates-io-heroku-metrics.example.com/drain
```

Finally you can add a scrape configuration to Prometheus gathering the metrics:

```yaml
- job_name: cratesio_heroku_metrics
  scheme: https
  basic_auth:
    username: metrics
    password: ${PASSWORD_METRICS}
  static_configs:
    - targets:
      - crates-io-heroku-metrics.example.com:443
```

In Rust's production environment the container is running on ECS Fargate.

## Rationale and requirements

To ensure smooth service operations the crates.io team needs to gather the
following metrics:

* **Service-level** metrics, such as the number of background jobs currently in
  the queue or how many crates were published recently. These metrics can be
  scraped from any of the application servers, as all application servers
  should return the same information.

* **Instance-level** metrics, such as the number of in-flight requests,
  response times or how many connections are available in the database pool.
  These metrics must be scraped from all application servers individually, as
  each server returns its own (different) metrics.

* **Heroku Postgres** metrics, such as the load average, the IOPS or the cache hit
  ratio.

The Rust Infrastructure team maintains a centralized monitoring solution based
on Prometheus, but unfortunately that makes integration with applications
running on Heroku hard.

While service-level work fine on Heroku (Prometheus will scrape them from one
application server at random thanks to Heroku's load balancer), the fact that
Heroku doesn't offer any way to reach the individual application servers makes
gathering instance-level metrics impossible with a centralized Prometheus
server. Heroku Postgres metrics aren't easier to gather either, as Heroku only
exposes them by periodically writing a line in the application logs.

Gathering Heroku Postgres metrics requires extracting them to the logs, so we
decided to scrape service-level metrics directly with Prometheus, and create a
single container (this!) to extract both Heroku Postgres and instance-level
metrics from the logs.

## Design

The container uses [nginx] to route and protect requests, and [Vector] to
ingest log messages and extract metrics out of them. Two password-protected
HTTP endpoints are exposed:

* `/drain`, which receives real-time log messages from [Heroku Logplex].
  Messages [are batched][logplex-batches]: we don't receive one request per
  log message.
* `/metrics`, which exposes the processed Prometheus metrics ready to be
  scraped.

How metrics are extracted depends on the kind of metric.

### Instance-level metrics

To gather instance-level metrics the container expects log messages in a
specific format. Each line must be prefixed with the
`crates-io-heroku-metrics:ingest` prefix, and must then contain the
Base64-encoded JSON-encoded metrics data. Metrics data is encoded with base64
to prevent other consumers of our logs (like Papertrail) from accidentally
parsing the contents of the metrics.

To simplify the logic inside the container the metric data must be serialized
according to [Vector's metric data model][data-model] (without the `timestamp`
field). An example is this line:

```
crates-io-heroku-metrics:ingest W3sibWV0cmljIjp7ImdhdWdlIjp7InZhbHVlIjowLjB9LCJraW5kIjoiYWJzb2x1dGUiLCJuYW1lIjoic2FtcGxlX2dhdWdlIiwidGFncyI6e319fV0=
```

Which encodes the `sample_gauge` gauge with a value of `0.0`:

```json
[
  {
    "metric": {
      "gauge": {
        "value": 0.0
      },
      "kind": "absolute",
      "name": "sample_gauge",
      "tags": {}
    }
  }
]
```

### Heroku Postgres metrics

Heroku Postgres metrics are extracted by parsing [the log lines emitted by
Heroku itself][heroku-postgres-metrics]. A Lua transform parses each line and
extracts the samples from it. There is no hardcoded list of metrics to extract,
so everything Heroku provides is exported.

[nginx]: https://nginx.org/
[Vector]: https://vector.dev/
[Heroku Logplex]: https://devcenter.heroku.com/articles/logplex
[heroku-postgres-metrics]: https://devcenter.heroku.com/articles/heroku-postgres-metrics-logs
[data-model]: https://vector.dev/docs/about/under-the-hood/architecture/data-model/metric/
[logplex-batches]: https://devcenter.heroku.com/articles/log-drains#https-drains
