# Phone login (design)

Used when `HOST` is not `127.0.0.1`/`localhost` (e.g. `HOST=0.0.0.0`), or
when `PUBLIC_URL` is set. On plain localhost there is no login.

The idea is like WhatsApp Web: pair your phone once, and the phone becomes
the key. Then you sign in any other browser by scanning its QR with the
phone.

## Flow
**1. Pair the phone (once).** At start, the server prints a QR in the
terminal (`qrencode -t ansiutf8`; without qrencode, just the link):
`<base>/pair?c=<code>`. The code works once and expires after 10 min.
Opening it gives a **phone cookie** and redirects to `/`. To pair another
phone, press Enter in the server terminal for a new code.

**2. Sign in a desktop.**
1. A browser with no valid cookie gets `login.html` at `/`.
2. It calls `POST /api/login/start`. The server makes a secret `wait` id
   (only this browser knows it) and a one-time `code` (2 min). It stores the
   browser's IP and User-Agent.
3. The page shows a QR of `<origin>/approve.html?c=<code>`.
4. The phone scans it. `approve.html` (phone cookie only) shows the IP and
   browser. Allow sends `POST /api/login/approve {code, allow: true}`.
5. The desktop polls `POST /api/login/poll {wait}` every 2 s. On `ok` the
   reply sets a **desktop cookie**, and the page goes to `/`.

## Cookies
- `k = <role>.<expiry>.<HMAC-SHA256(secret, "role.expiry")>`, HttpOnly,
  SameSite=Lax, Secure with TLS. Role `p` = phone, `d` = desktop.
- The server checks the HMAC and that the expiry is in the future. Editing
  the role or the date breaks the HMAC.
- Lifetimes: `PHONE_DAYS` (default 365), `LOGIN_HOURS` (default 24).
- Only a phone cookie can approve. A desktop can't sign in other browsers.

## Secret
- `TOKEN` env if set, else a random key kept in
  `~/.cache/repo-chat/secret` (mode 600, outside the repo).
- It only signs cookies. It never goes over the network.
- A restart keeps every login. To sign everyone out, delete the file (or
  change `TOKEN`) and restart.

## What each check stops
| Threat | Check |
|---|---|
| Someone opens the site | No cookie: only `/`, `login.html`, `style.css`, `/pair`, login start/poll. All else 403 |
| Someone scans a desktop QR | `approve.html` needs a phone cookie |
| Someone photographs the QR | The code only lets the phone approve; the cookie goes to the `wait` holder |
| Someone shows you their QR | The phone shows their IP and browser; you must tap Allow |
| Reused or old codes | One use; pair 10 min, sign-in 2 min |
| Many start calls | At most 20 sign-ins waiting |
| Another site posts to the API | Origin must equal the server's own |
| Stolen cookie | Expires; delete the secret to cancel all |

## HTTPS
- On the network, HTTPS is on by default (a self-signed cert in
  `~/.cache/repo-chat/`, or your own `CERT`/`KEY`). Each browser warns
  once. `TLS=0` turns it off; then others on the Wi-Fi can read cookies.
- Cookies get `Secure` when the server or `PUBLIC_URL` uses HTTPS.

## Behind a proxy or tunnel
Set `PUBLIC_URL=https://chat.example.com` and keep `HOST=127.0.0.1`.
- Login is on, even on 127.0.0.1. Without `PUBLIC_URL`, a site on
  127.0.0.1 has no login, so anyone who reaches the proxy can see it.
- The proxy does HTTPS; the server speaks plain HTTP to it.
- The pair QR uses `PUBLIC_URL`. API calls must come from that origin (or
  the server's own address).
- For requests from 127.0.0.1 only, the approve page shows the IP from
  `CF-Connecting-IP`, else the first `X-Forwarded-For` entry. It is only
  a hint: if the proxy passes these headers from the client unchanged,
  they can be faked.
- As a service there is no terminal: the pair link goes to the log (e.g.
  `journalctl`), and Enter does not work. Restart for a new pair link.
  Show it as a QR in your terminal and scan it with the phone:
  `qrencode -t ansiutf8 "$(journalctl --user -u <service> -o cat | grep -o 'https://[^ ]*/pair?c=[^ ]*' | tail -1)"`

## Don't send the pair link through a chat app
Telegram, Slack, WhatsApp and others open a link to build its preview.
That uses the one-time code before you tap it, and your tap gets
"used or expired". Scan the QR instead, or turn off the link preview.

## Limits
- The camera opens links in the phone's default browser. The phone cookie
  lives there. If another browser opens an approve link, the page says it
  is not paired.
- Pending codes live in memory. A restart cancels them, not the cookies.
