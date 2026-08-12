import assert from 'node:assert/strict';
import test from 'node:test';

import { consumeSseStream } from './sse.js';

test('parses SSE events split across network chunks', async () => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('data: {"type":"pro'));
      controller.enqueue(encoder.encode('gress","data":{"progress":30}}\n\n'));
      controller.enqueue(encoder.encode('data: {"type":"complete"}\r\n\r\n'));
      controller.close();
    },
  });
  const events = [];

  await consumeSseStream(stream, (event) => events.push(event));

  assert.deepEqual(events, [
    { type: 'progress', data: { progress: 30 } },
    { type: 'complete' },
  ]);
});

test('rejects malformed event payloads', async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: not-json\n\n'));
      controller.close();
    },
  });

  await assert.rejects(() => consumeSseStream(stream, () => {}), SyntaxError);
});
