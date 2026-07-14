import http from 'k6/http';
import { check, sleep, group } from 'k6';

const PAI = 'http://localhost:8080';
const FILHO = 'http://localhost:3000';

export const options = {
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% das reqs < 2s
    http_req_failed: ['rate<0.05'],     // < 5% de erro
  },
  scenarios: {
    pai_stress: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '20s', target: 3 },   // sobe para 3 VUs
        { duration: '30s', target: 3 },   // mantém 3 VUs
        { duration: '10s', target: 0 },   // desce
      ],
      exec: 'testPai',
      gracefulRampDown: '5s',
    },
    filho_stress: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '10s', target: 2 },
        { duration: '20s', target: 2 },
        { duration: '5s', target: 0 },
      ],
      exec: 'testFilho',
      gracefulRampDown: '5s',
    },
  },
};

export function testPai() {
  // Endpoints leves (cache)
  group('Pai - stats (cache)', () => {
    let res = http.get(`${PAI}/stats`, { timeout: '10s' });
    check(res, { 'stats 200': (r) => r.status === 200 });
    sleep(1);
  });

  group('Pai - totais/uf (cache)', () => {
    let res = http.get(`${PAI}/totais/uf`, { timeout: '10s' });
    check(res, { 'totais 200': (r) => r.status === 200 });
    sleep(1);
  });

  // Dashboard HTML (estático, leve)
  group('Pai - dashboard', () => {
    let res = http.get(`${PAI}/dashboard`, { timeout: '10s' });
    check(res, { 'dashboard 200': (r) => r.status === 200 });
    sleep(1);
  });

  // Treemap HTML (estático)
  group('Pai - treemap HTML', () => {
    let res = http.get(`${PAI}/treemap`, { timeout: '10s' });
    check(res, { 'treemap HTML 200': (r) => r.status === 200 });
    sleep(1);
  });

  // Treemap JSON (pesado – agregação de 5.9M linhas, mas com cache do lado do servidor)
  group('Pai - treemap/brasil JSON', () => {
    let res = http.get(`${PAI}/treemap/brasil?nivel=uf_fonte`, { timeout: '15s' });
    check(res, { 'treemap JSON 200': (r) => r.status === 200 });
    check(res, { 'treemap JSON contem Brasil': (r) => r.body && r.body.includes('Brasil') });
    sleep(2); // espera mais para não sobrecarregar
  });

  // Geração ao vivo (leve)
  group('Pai - geracao/atual', () => {
    let res = http.get(`${PAI}/geracao/atual`, { timeout: '10s' });
    check(res, { 'geracao 200': (r) => r.status === 200 });
    sleep(1);
  });

  // IoT saldo (leve)
  group('Pai - IoT saldo', () => {
    let res = http.get(`${PAI}/iot/saldo?cliente_id=1`, { timeout: '10s' });
    check(res, { 'IoT saldo 200': (r) => r.status === 200 });
    sleep(1);
  });
}

export function testFilho() {
  group('Filho - / (HTML)', () => {
    let res = http.get(`${FILHO}/`, { timeout: '10s' });
    check(res, { 'filho 200': (r) => r.status === 200 });
    sleep(2);
  });
}
