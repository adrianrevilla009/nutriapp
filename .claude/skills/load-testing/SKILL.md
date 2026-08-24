---
description: Load/performance testing conventions for NutriApp using k6. Use whenever writing a load test script, defining an SLO target, or discussing whether a change needs performance validation before prod promotion.
---

# Load Testing Conventions — NutriApp

Full policy: `docs/performance-testing.md`. SLO targets per service:
`docs/observability-slo.md`.

## Rules
- k6 for HTTP load tests, scripts live in `tests/load/<service-name>/`.
- Load tests never run against real third-party vision/LLM APIs uncapped —
  use sandbox endpoints or a strict pre-agreed request budget
  (`docs/performance-testing.md` section 6).
- Not run on every PR. Run against `staging` before any prod promotion that
  touches a hot path listed in `docs/performance-testing.md` section 2.
- A missed SLO in a load test blocks prod promotion — the human decides
  whether to accept a documented temporary regression.

## Test Script Skeleton (k6)
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    load: { executor: 'ramping-vus', startVUs: 0, stages: [
      { duration: '2m', target: 50 },
      { duration: '5m', target: 50 },
      { duration: '2m', target: 0 },
    ]},
  },
  thresholds: {
    http_req_duration: ['p(95)<250'], // match the SLO for the endpoint under test
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.post(`${__ENV.BASE_URL}/api/v1/logs`, JSON.stringify({/* ... */}), {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${__ENV.TOKEN}` },
  });
  check(res, { 'status is 201': (r) => r.status === 201 });
  sleep(1);
}
```
