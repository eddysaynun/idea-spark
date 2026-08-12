const UPSTREAM_ORIGIN = 'http://qwen-origin.heyedwardchen.com:6091';
const ALLOWED_PATHS = new Set(['/v1/models', '/v1/chat/completions']);

function unauthorized() {
  return new Response(JSON.stringify({ error: { message: 'Unauthorized' } }), {
    status: 401,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

function constantTimeEqual(left, right) {
  const encoder = new TextEncoder();
  const leftBytes = encoder.encode(left);
  const rightBytes = encoder.encode(right);
  const length = Math.max(leftBytes.length, rightBytes.length);
  let difference = leftBytes.length ^ rightBytes.length;

  for (let index = 0; index < length; index += 1) {
    difference |= (leftBytes[index] || 0) ^ (rightBytes[index] || 0);
  }
  return difference === 0;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!ALLOWED_PATHS.has(url.pathname)) {
      return new Response('Not found', { status: 404 });
    }

    const expected = `Bearer ${env.PROXY_API_KEY}`;
    const actual = request.headers.get('authorization') || '';
    if (!env.PROXY_API_KEY || !constantTimeEqual(actual, expected)) {
      return unauthorized();
    }

    const headers = new Headers(request.headers);
    headers.delete('host');
    headers.delete('cf-connecting-ip');
    headers.delete('cf-ipcountry');
    headers.delete('cf-ray');
    headers.delete('x-forwarded-proto');
    headers.delete('x-real-ip');

    const upstreamUrl = `${UPSTREAM_ORIGIN}${url.pathname}${url.search}`;
    try {
      const upstream = await fetch(upstreamUrl, {
        method: request.method,
        headers,
        body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
        redirect: 'manual',
      });

      return new Response(upstream.body, {
        status: upstream.status,
        headers: upstream.headers,
      });
    } catch (error) {
      console.error(JSON.stringify({
        event: 'model_proxy_error',
        path: url.pathname,
        error: error instanceof Error ? error.message : String(error),
      }));
      return new Response(JSON.stringify({ error: { message: 'Upstream unavailable' } }), {
        status: 502,
        headers: { 'content-type': 'application/json; charset=utf-8' },
      });
    }
  },
};
