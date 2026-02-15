/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — k6 Load Test
   Target: 500 QPS sustained, p95 < 500ms
   ═══════════════════════════════════════════════════════════ */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ─── Custom Metrics ───
const errorRate = new Rate('kf_errors');
const queryDuration = new Trend('kf_query_duration', true);

// ─── Test Configuration ───
export const options = {
    stages: [
        { duration: '30s', target: 10 },   // Warm-up
        { duration: '1m', target: 100 },  // Ramp to 100 VUs
        { duration: '2m', target: 100 },  // Sustain 100 VUs
        { duration: '1m', target: 300 },  // Ramp to 300 VUs
        { duration: '2m', target: 300 },  // Sustain 300 VUs
        { duration: '1m', target: 500 },  // Peak: 500 VUs
        { duration: '2m', target: 500 },  // Sustain peak
        { duration: '30s', target: 0 },    // Cool-down
    ],
    thresholds: {
        'http_req_duration': ['p(95)<500', 'p(99)<1000'],
        'kf_errors': ['rate<0.01'],        // < 1% error rate
        'kf_query_duration': ['p(95)<500'],
        'http_req_failed': ['rate<0.01'],
    },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

const QUERIES = [
    'What encryption standards does our platform use?',
    'What is our data retention policy?',
    'How does RBAC work?',
    'What monitoring alerts are configured?',
    'How are prompt injection attacks prevented?',
    'What file formats are supported for upload?',
    'What is the p95 latency target?',
    'How does the LLM router decide which model to use?',
    'What PII types does the output filter detect?',
    'What are the EU AI Act requirements?',
];

// ─── Main Test ───
export default function () {
    const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];

    const payload = JSON.stringify({
        query: query,
        options: {
            model: 'auto',
            use_deep_search: false,
            use_multi_hop: false,
        },
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Tenant-ID': 'load-test-tenant',
        },
        timeout: '10s',
    };

    const res = http.post(`${BASE_URL}/v1/query`, payload, params);

    queryDuration.add(res.timings.duration);

    const passed = check(res, {
        'status is 200': (r) => r.status === 200,
        'response has body': (r) => r.body && r.body.length > 0,
        'latency < 1s': (r) => r.timings.duration < 1000,
    });

    errorRate.add(!passed);

    sleep(0.1 + Math.random() * 0.3); // 100-400ms think time
}

// ─── Lifecycle Hooks ───
export function setup() {
    // Verify API is reachable
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
        'API is healthy': (r) => r.status === 200,
    });
    return { startTime: new Date().toISOString() };
}

export function teardown(data) {
    console.log(`Load test completed. Started at: ${data.startTime}`);
}
