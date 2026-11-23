/**
 * Upload notifier for the gjannu site (Cloudflare Worker).
 *
 * YouTube sends a WebSub (PubSubHubbub) notification through Google's hub
 * when the channel uploads a video or changes a title or a description.
 * This Worker checks the notification and starts the GitHub workflow
 * "Update and deploy" with a repository_dispatch event.
 *
 * Routes:
 *   GET  /            Shows the status of the configuration. It shows no secret values.
 *   GET  /websub      The hub sends the verification request here. The Worker returns hub.challenge.
 *   POST /websub      The hub sends the notification here.
 *   GET  /subscribe   Asks the hub for a new subscription. Use it once after the deployment.
 *
 * The cron trigger in wrangler.toml renews the subscription every 2 days.
 *
 * Variables (wrangler.toml): CHANNEL_ID
 * Secrets (wrangler secret put): GITHUB_TOKEN, GITHUB_REPO, HUB_SECRET
 */

const HUB = "https://pubsubhubbub.appspot.com/subscribe";
// The hub keeps a subscription for about 10 days at most. Ask for 5 days and renew every 2 days.
const LEASE_SECONDS = 432000;

function topicUrl(env) {
  return `https://www.youtube.com/xml/feeds/videos.xml?channel_id=${env.CHANNEL_ID}`;
}

function text(body, status = 200) {
  return new Response(body, { status, headers: { "content-type": "text/plain; charset=utf-8" } });
}

/** Send a subscribe request to the hub. The hub then calls GET /websub to verify it. */
async function subscribe(env, callback) {
  const form = new URLSearchParams({
    "hub.callback": callback,
    "hub.topic": topicUrl(env),
    "hub.mode": "subscribe",
    "hub.verify": "async",
    "hub.lease_seconds": String(LEASE_SECONDS),
    "hub.secret": env.HUB_SECRET,
  });
  const r = await fetch(HUB, { method: "POST", body: form });
  return { status: r.status, body: await r.text() };
}

/** Compare the X-Hub-Signature header with the HMAC-SHA1 of the body. */
async function validSignature(env, header, body) {
  if (!header || !header.startsWith("sha1=")) return false;
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(env.HUB_SECRET), { name: "HMAC", hash: "SHA-1" }, false, ["sign"]
  );
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, body));
  const hex = Array.from(mac, (b) => b.toString(16).padStart(2, "0")).join("");
  const given = header.slice(5).toLowerCase();
  if (given.length !== hex.length) return false;
  let diff = 0;
  for (let i = 0; i < hex.length; i++) diff |= hex.charCodeAt(i) ^ given.charCodeAt(i);
  return diff === 0;
}

/** Start the GitHub workflow. */
async function dispatch(env, videoId) {
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "gjannu-notify",
      "content-type": "application/json",
    },
    body: JSON.stringify({ event_type: "youtube-video", client_payload: { video_id: videoId } }),
  });
  return r.status;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const callback = `${url.origin}/websub`;

    if (url.pathname === "/") {
      const missing = ["CHANNEL_ID", "GITHUB_TOKEN", "GITHUB_REPO", "HUB_SECRET"].filter((k) => !env[k]);
      return text(
        missing.length
          ? `Not ready. Set these values: ${missing.join(", ")}`
          : `Ready.\nChannel: ${env.CHANNEL_ID}\nRepository: ${env.GITHUB_REPO}\nCallback: ${callback}\nOpen /subscribe once to start the subscription.`
      );
    }

    if (url.pathname === "/subscribe" && request.method === "GET") {
      const r = await subscribe(env, callback);
      // The hub returns 202 when it accepts the request. It then verifies it with GET /websub.
      return text(
        r.status === 202
          ? "Subscription request accepted. The hub now verifies it. Notifications start in a few seconds."
          : `The hub refused the request (HTTP ${r.status}): ${r.body}`,
        r.status === 202 ? 200 : 502
      );
    }

    if (url.pathname !== "/websub") return text("Not found", 404);

    // Verification from the hub: return hub.challenge only for our own topic.
    if (request.method === "GET") {
      const mode = url.searchParams.get("hub.mode");
      const topic = url.searchParams.get("hub.topic");
      const challenge = url.searchParams.get("hub.challenge");
      if (challenge && topic === topicUrl(env) && (mode === "subscribe" || mode === "unsubscribe")) {
        return text(challenge);
      }
      return text("Unknown topic", 404);
    }

    if (request.method === "POST") {
      const body = await request.arrayBuffer();
      // Always answer 2xx, so that the hub does not send the message again.
      // Ignore a message that has a wrong signature.
      if (!(await validSignature(env, request.headers.get("x-hub-signature"), body))) {
        return new Response(null, { status: 204 });
      }
      const xml = new TextDecoder().decode(body);
      const videoId = (xml.match(/<yt:videoId>([A-Za-z0-9_-]{11})<\/yt:videoId>/) || [])[1];
      const channelId = (xml.match(/<yt:channelId>([^<]+)<\/yt:channelId>/) || [])[1];
      // A deleted video has no yt:videoId. The weekly job handles it.
      if (videoId && channelId === env.CHANNEL_ID) {
        ctx.waitUntil(dispatch(env, videoId).then((s) => console.log(`dispatch ${videoId}: HTTP ${s}`)));
      }
      return new Response(null, { status: 204 });
    }

    return text("Method not allowed", 405);
  },

  /** The cron trigger renews the subscription before it expires. */
  async scheduled(event, env, ctx) {
    if (!env.WORKER_URL) {
      console.log("WORKER_URL is not set. The subscription is not renewed.");
      return;
    }
    const r = await subscribe(env, `${env.WORKER_URL.replace(/\/$/, "")}/websub`);
    console.log(`renew: HTTP ${r.status}`);
  },
};
