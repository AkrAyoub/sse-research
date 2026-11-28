# V4 web dashboard publication
The application installer accepts --publish-web as explicit opt-in, no extra
prompt. Separate public console on loopback 8791; private console 8790 is never
forwarded. Public mode supports chain views and unsigned transaction intent
preparation; local upload and provider fetch are unavailable. No signing keys
or private state passed to public service. The cloudflared binary uses the
previously reviewed version/hash from R334, not an unpinned download. HTTPS
verification compares public mode and per-host nonsecret instance ID via the
current tunnel PID's announced URL. Quick tunnels depend on Cloudflare,
may rotate URLs and are not production SLA hosting. Public readiness is not
role activation. Existing V4 installations can publish without reinstalling
using scripts/sse_v4_publish_web.py --apply in the V4 virtualenv. No native
services or existing V3 tunnels modified. Requires actual live verification;
not executed in source session.
