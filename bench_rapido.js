import http from 'k6/http';
import { check, group } from 'k6';

export default function () {
  group('Pai /stats', () => {
    let res = http.get('http://localhost:8080/stats', { timeout: '5s' });
    check(res, { 'status 200': (r) => r.status === 200 });
  });
  group('Pai /totais', () => {
    let res = http.get('http://localhost:8080/totais/uf', { timeout: '5s' });
    check(res, { 'status 200': (r) => r.status === 200 });
  });
  group('Filho /', () => {
    let res = http.get('http://localhost:3000/', { timeout: '5s' });
    check(res, { 'status 200': (r) => r.status === 200 });
  });
}
