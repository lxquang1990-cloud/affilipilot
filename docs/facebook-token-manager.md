# Facebook Token Manager

AffiliPilot can manage Facebook token lifecycle without printing token values.

Supported flow:

1. Inspect current Page token.
2. Exchange a short-lived User token into a long-lived User token.
3. Derive a Page token from a valid long-lived User token.
4. Refresh the long-lived User token before it expires, then derive a fresh Page token.

## Secret keys

Stored in `/home/snail/.openclaw/workspace/secrets/affilipilot.env`:

```text
FACEBOOK_APP_ID=.placeholder
FACEBOOK_APP_SECRET=.placeholder
FACEBOOK_PAGE_ID=.placeholder
FACEBOOK_PAGE_ACCESS_TOKEN=.placeholder
FACEBOOK_USER_ACCESS_TOKEN=.placeholder
FACEBOOK_USER_TOKEN_EXPIRES=.placeholder-date
```

Do not paste token values into chat. Edit the secret file locally or pass tokens through a secure shell session.

## Inspect current page token

```bash
python3 -m affilipilot facebook-token-manager --action inspect
```

This wraps the existing Facebook token check and does not print secret values.

## Exchange short-lived User token

Get a short-lived User token from Meta Graph API Explorer / Facebook Login with required permissions, then run locally:

```bash
python3 -m affilipilot facebook-token-manager \
  --action exchange \
  --short-token '.short-lived-user-token-placeholder'
```

The command:

- exchanges it for a long-lived User token
- calls `/me/accounts`
- finds `FACEBOOK_PAGE_ID`
- writes `FACEBOOK_USER_ACCESS_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`, and `FACEBOOK_USER_TOKEN_EXPIRES`
- chmods the secret file to `600`
- never prints token values

## Derive Page token from existing User token

```bash
python3 -m affilipilot facebook-token-manager --action page-token
```

Use this when `FACEBOOK_USER_ACCESS_TOKEN` is already valid but Page token needs updating.

## Refresh long-lived User token

```bash
python3 -m affilipilot facebook-token-manager --action refresh
```

For cron-style guarded refresh:

```bash
python3 -m affilipilot facebook-token-manager --action refresh --auto --threshold-days 15
```

`--auto` skips refresh when the stored `FACEBOOK_USER_TOKEN_EXPIRES` is still farther away than the threshold.

## Limitations

- Expired User tokens cannot be renewed offline. You must perform OAuth again and run `--action exchange` with a fresh short-lived User token.
- Page tokens derived from long-lived User tokens can still become invalid if app permissions, password/session, Page role, or Business settings change.
- Real Facebook publish remains gated by `facebook-token-check`, approval status, compliance, affiliate link, media, and dry-run plan.
