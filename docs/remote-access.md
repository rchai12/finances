# Reaching the site from the household's other devices

The app never listens beyond the Mac it runs on: `fin web serve` binds to 127.0.0.1 only. The household's phones and laptops reach it through **Tailscale Serve**, which gives the Mac a private HTTPS address on the household's own tailnet and forwards each request to the app on loopback. The encryption ends on the Mac itself, never on a third party's server. Every page then needs the household password (Phase 20).

This runbook sets that up once, on the Mac that runs the app (the Mac Studio).

## 1. Set the household password

```sh
.venv/bin/fin web password
```

It asks for the new password twice (12 to 200 characters) and keeps only its scrypt hash in the macOS Keychain (service `finances-web`). Changing it later asks for the current one first and ends every session on every device. Without a password the server will not start.

## 2. Install Tailscale on every household device

- Install Tailscale on the Mac and on each phone and laptop the household uses, and log in to the same tailnet.
- In the Tailscale admin console, admit only the household's own devices, and turn on **MagicDNS** and **HTTPS certificates**.
- Note the Mac's name, shown by `tailscale status` on the Mac: something like `mac-studio.tail1234.ts.net`.

## 3. Tell the app its name

Add the name to `.env` in the repository folder on the Mac (never committed):

```sh
FIN_WEB_HOSTNAME=mac-studio.tail1234.ts.net
```

The app then also answers to that name, accepts forms sent from `https://` that name, and marks its cookies `Secure` for requests that arrive through it.

## 4. Keep the server running

```sh
scripts/install-web-service.sh
```

It installs a launchd job that starts `fin web serve` at login and again whenever it stops; the log is `data/logs/web.log`. Remove it with `scripts/uninstall-web-service.sh`.

**After every code update** (a phase committed, a `git pull`), restart the server so it runs the new code:

```sh
launchctl kickstart -k gui/$(id -u)/local.finances.web
```

A running server keeps the Python code it started with but reads its page templates fresh from disk, so after an update the two disagree until it restarts, and a changed page fails with "Internal Server Error".

## 5. Publish it on the tailnet

```sh
tailscale serve --bg 8765
```

(8765 is `FIN_WEB_PORT`, the default.) Tailscale Serve then forwards `https://mac-studio.tail1234.ts.net` to `http://127.0.0.1:8765` on the Mac. Never use **Funnel**, which would publish the site to the internet.

## 6. Check it

```sh
.venv/bin/fin doctor
```

It must end without a failure: `Web address` is always `http://127.0.0.1:8765 (loopback only)`, `Web password` is `set OK`, and `Tailscale name` shows the name.

Then open `https://mac-studio.tail1234.ts.net` on a phone: the login page appears. In a desktop browser's developer tools, the `fin_session` cookie is marked `Secure` and `HttpOnly`.

## When something goes wrong

- **Locked out after wrong passwords.** On the Mac: `.venv/bin/fin web unlock` (it asks for the password).
- **The password is forgotten.** Open Keychain Access on the Mac, delete the items of service `finances-web`, then run `fin web password` again. Every session ends.
- **A device is lost.** Remove it from the tailnet in the Tailscale admin console, then run `fin web password` to end every session.
- **"Bad host" in the browser.** `FIN_WEB_HOSTNAME` is missing or differs from the name in the address bar; restart the server after changing `.env` (`scripts/install-web-service.sh` again restarts it).
- **"Internal Server Error" on a page after an update.** The server is still running the old code; restart it as in section 4.
- **"could not use the system keychain".** The Mac's login Keychain is locked; the site refuses every page until it can read it again.
