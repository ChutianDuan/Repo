# Project invariants

- Non-SSE APIs return `{code, message, data}` for both success and errors.
- SSE data includes a `type`; emitted events have increasing `id` values and end with `done` or `error`.
- Resume SSE with `Last-Event-ID`. Generation must continue after client disconnect, and expired resume state must fail instead of restarting work.
- Persist the final message and citations before emitting `done`.
- Keep routers thin; move reusable transport and business logic into focused modules.
