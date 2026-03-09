/**
 * AWS client factory.
 *
 * In mock mode (CONFIG.MOCK=true): all calls go to the local mock server /api/*
 * In live mode (CONFIG.MOCK=false): real AWS SDK v3 clients using credentials
 *   injected into CONFIG.credentials by mock-server.py --live
 *
 * Usage:
 *   import { getClients } from '../aws.js';
 *   const { dynamo, datazone, ssm, lambda, identityStore } = await getClients();
 */

import { CONFIG } from './config.js';

// ── Mock client (wraps fetch to /api/*) ──────────────────────────────────────

function mockClient(service) {
  return {
    _service: service,
    send: async (cmd) => {
      const name = cmd.constructor.name;
      const input = cmd.input || {};
      const res = await fetch(`${CONFIG.API_URL}/_sdk/${service}/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ message: res.statusText }));
        throw Object.assign(new Error(err.message || res.statusText), { name: err.code || 'Error' });
      }
      return res.json();
    }
  };
}

// ── Live clients (real AWS SDK v3) ────────────────────────────────────────────

let _clients = null;

export async function getClients() {
  if (_clients) return _clients;

  if (CONFIG.MOCK) {
    // Mock mode — all calls go to local server
    _clients = {
      dynamo:        mockClient('dynamodb'),
      datazone:      mockClient('datazone'),
      ssm:           mockClient('ssm'),
      lambda:        mockClient('lambda'),
      identityStore: mockClient('identitystore'),
    };
    return _clients;
  }

  // Live mode — use AWS SDK v3 loaded from CDN script tags
  // The SDK globals are set by the CDN bundles:
  //   window.AWS_DynamoDB, window.AWS_DataZone, etc.
  const creds = {
    accessKeyId:     CONFIG.credentials.accessKeyId,
    secretAccessKey: CONFIG.credentials.secretAccessKey,
    sessionToken:    CONFIG.credentials.sessionToken,
  };
  const region = CONFIG.region;

  // SDK v3 browser globals (set by CDN script tags in each HTML file)
  const DynamoDBClient        = window.AWS_DynamoDB?.DynamoDBClient;
  const DataZoneClient        = window.AWS_DataZone?.DataZoneClient;
  const SSMClient             = window.AWS_SSM?.SSMClient;
  const LambdaClient          = window.AWS_Lambda?.LambdaClient;
  const IdentityStoreClient   = window.AWS_IdentityStore?.IdentityStoreClient;

  if (!DynamoDBClient) {
    throw new Error('AWS SDK not loaded. Check CDN script tags in index.html.');
  }

  _clients = {
    dynamo:        new DynamoDBClient({ region, credentials: creds }),
    datazone:      new DataZoneClient({ region, credentials: creds }),
    ssm:           new SSMClient({ region, credentials: creds }),
    lambda:        new LambdaClient({ region, credentials: creds }),
    identityStore: new IdentityStoreClient({ region, credentials: creds }),
  };
  return _clients;
}

// ── Convenience: reset clients (e.g. after credential refresh) ───────────────
export function resetClients() { _clients = null; }
