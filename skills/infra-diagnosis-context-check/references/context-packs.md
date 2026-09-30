# Context packs — read-only commands per stack

Ask for the smallest set that discriminates between hypotheses, not the whole pack.

## Always worth having

```bash
git log --oneline -20
git log --since="3 days ago" --stat
```
Plus: which env, was it ever working, last known-good time, all traffic/replicas or some.
Raw error output, unparaphrased, with timestamps.

## Kubernetes

```bash
kubectl -n <ns> describe pod <pod>              # events at bottom are usually the answer
kubectl -n <ns> logs <pod> --previous --tail=200 # --previous catches the crash
kubectl -n <ns> get events --sort-by=.lastTimestamp | tail -40
kubectl -n <ns> get deploy <name> -o yaml       # applied spec, not the chart
kubectl -n <ns> get svc,endpoints               # does the Service have endpoints at all?
kubectl -n <ns> describe ingress <name>
kubectl get nodes -o wide                       # scheduling/capacity
kubectl auth can-i <verb> <res> --as=system:serviceaccount:<ns>:<sa>
kubectl version --short
```

Trap: `CrashLoopBackOff` covers bad image, missing env, failing probe, OOMKill, missing volume. Only `describe` (termination reason + exit code) plus `logs --previous` separate them. Don't guess between them.

## Helm

`values.yaml` is one layer of a merge; the rendered manifest is what ran. Base → env overlay → CI `--set` flags is exactly where reality diverges from the pasted file.

```bash
helm -n <ns> get manifest <release>          # highest value: what is deployed now
helm -n <ns> get values <release> --all      # merged values incl. defaults
helm -n <ns> history <release>
helm template <rel> <chart> -f values.yaml -f values-<env>.yaml
cat <chart>/Chart.yaml                       # chart version + subchart pins
```

Ask: does CI pass extra `--set` flags? They appear in no repo file and win the merge.

## Terraform

Repo = intent, state = reality. Never reason from `.tf` alone.

```bash
terraform plan -no-color
terraform plan -refresh-only -no-color       # pure drift
terraform state list && terraform state show <address>
terraform version && head -40 .terraform.lock.hcl
terraform workspace show
grep -rn "source\s*=" --include="*.tf" .     # module pins
```

Ask: **does anything else manage this resource?** Another repo, console change, operator, separate pipeline. Shared ownership is invisible in one repo and explains behavior no code reading can.

## Cloud provider

```bash
aws sts get-caller-identity                  # which account/role is even in use
aws logs tail /aws/<path> --since 1h
aws cloudtrail lookup-events --max-results 20
gcloud config list && gcloud logging read 'severity>=ERROR' --limit 20 --freshness=1h
az account show
```

Audit logs answer "did a human change this outside IaC," which explains a large share of otherwise inexplicable behavior.

## CI/CD and multi-repo

- Which pipeline and which run deployed this? Link the log.
- Does the pipeline inject values, image tags, or flags absent from the repo?
- Which SHA is actually running? Deployed image tag vs. repo HEAD disagree more often than expected.
- Does more than one repo or pipeline touch this namespace/resource?

## Networking, DNS, TLS

Locate the first failing hop; pod→svc, svc→ingress, ingress→internet, and DNS vs TLS vs routing look identical from a browser but need different fixes.

```bash
kubectl -n <ns> run tmp --rm -it --image=nicolaka/netshoot -- /bin/bash
  # curl -v <svc>.<ns>.svc.cluster.local:<port> ; nslookup <host> ; nc -zv <host> <port>
dig +short <host> ; dig +trace <host>
curl -vso /dev/null https://<host>
openssl s_client -connect <host>:443 -servername <host> </dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer
kubectl -n <ingress-ns> logs deploy/<controller> --tail=100
```

## Redaction

Never needed: secret values, keys, tokens, `.tfstate` credentials.
Needed and usually safe: resource names, namespaces, image tags, versions, event and error text, structural YAML.
**Redact consistently** — if `prod-db-1` becomes `db-A`, keep it `db-A` everywhere; inconsistent redaction breaks correlation and has caused wrong diagnoses on its own. Keep timestamps intact; ordering is often the whole answer.

## Low access: console, CloudWatch, or symptom only

Common in orgs where prod CLI access is restricted. Establish the access level before asking for anything.

### CloudWatch Logs Insights

Substitute for `kubectl logs` when the cluster ships logs to CloudWatch. Give the user the query, not a description of it.

```
# Errors in a window, newest first
fields @timestamp, @message
| filter @message like /(?i)(error|exception|fatal|panic)/
| sort @timestamp desc
| limit 100

# Restart / OOM evidence
fields @timestamp, @message
| filter @message like /(?i)(oomkill|out of memory|liveness|readiness|terminated|SIGTERM)/
| sort @timestamp desc

# Group error volume over time — finds the onset moment
fields @timestamp
| filter @message like /(?i)error/
| stats count() by bin(5m)

# EKS control plane / container insights
fields @timestamp, kubernetes.pod_name, log
| filter kubernetes.namespace_name = "<ns>"
| sort @timestamp desc
```

Ask them to set the time range to span the last known-good moment, not just the failure — the transition is what identifies the cause.

### Console substitutes

| Wanted | Console equivalent |
|---|---|
| `kubectl describe pod` events | EKS console → Workloads → pod → Events tab |
| `kubectl logs --previous` | CloudWatch log group, filter to that pod, window before restart |
| `terraform state show` | Resource's own console page — compare fields to expected |
| Manual changes outside IaC | CloudTrail → Event history, filter by resource name |
| `helm get values` | CI job log for the deploy run; the rendered values often print there |
| Which SHA is running | Image tag on the console workload page, or the deploy pipeline run |
| `kubectl top` | CloudWatch Container Insights, or APM (Datadog/Grafana) |
| Service endpoints / health | Target group health in the ALB/NLB console |

### Symptom-only inference

Narrows the space without any access. Not conclusive — state which hypotheses remain live.

- **502 vs 503 vs 504** — 502: upstream returned garbage or died mid-response. 503: no healthy target at all. 504: upstream too slow. These point at different layers.
- **Timeout duration is a fingerprint** — a clean 60s often means ALB idle timeout, 30s a common gateway/proxy default, 5s a client or service-mesh setting. The exact number identifies which component gave up.
- **Intermittent at a stable ratio** — suggests a subset of replicas or targets is bad; ~50% failure with two replicas is one broken pod. Constant failure suggests config, not capacity.
- **Fails for some users/paths only** — routing, per-tenant config, or a cached DNS answer; not a whole-service outage.
- **Works then degrades over hours** — leak, connection-pool exhaustion, disk fill, token expiry.
- **Failed exactly at a deploy, cert renewal, or cron time** — correlate the onset timestamp against those schedules before anything else.

### The escalation ask

When nothing at their access level discriminates, produce a forwardable request:

```
Blocked on: [which hypotheses this would separate]
Please run: [exact command]
Meaning: if output shows X → [hypothesis A]; if Y → [hypothesis B]
Window: [timestamps spanning last known-good → failure]
Safe: read-only, no changes
```
