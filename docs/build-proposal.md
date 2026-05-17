# AffiliPilot Lite — Build Proposal & MVP Spec

## 1. Mission

AffiliPilot Lite is a money-first affiliate operating assistant for SnailBot. Its first job is not to build a beautiful AI automation platform; its first job is to help Snail consistently create, review, publish, and learn from Shopee affiliate content via Accesstrade.

Initial channel: Facebook Page `Nâng Niu Trái Ngọt Tình Yêu`.

Initial niche: mother/baby, constrained to low-risk utility products.

## 2. Current facts

- User goal: earn money from Shopee affiliate.
- Affiliate network: Accesstrade.
- Accesstrade API token: not available yet; user will provide later.
- Facebook Page: existing, ~3,200 followers.
- Control plane: Telegram approval.
- LLM budget: 20k-30k VND/day.
- Future expansion: AI videos for Facebook, TikTok, YouTube.

## 3. Strategic decision

Build a small, reversible MVP first.

Do not build the full infographic system immediately. The first evidence loop is:

```text
product links → scored candidates → compliant Vietnamese drafts → Telegram approval → publish/fallback → daily digest
```

## 4. Sprint 0 Scope

Sprint 0 creates the safe foundation and proves the workflow shape before any real token/API/publishing work.

Deliverables:

- Project scaffold.
- Build proposal.
- Mother/baby compliance policy.
- Tracking/sub_id strategy.
- Example product input format.
- Product scoring skeleton.
- Compliance checker skeleton.
- Telegram approval data model skeleton.
- Verification script and tests.

Sprint 0 does **not** call Accesstrade, does **not** publish to Facebook, and does **not** require secrets.

## 5. Sprint 1 Scope

Sprint 1 implements an assisted workflow:

1. Snail provides 20-50 Shopee/Accesstrade product links via Telegram or file.
2. System normalizes product records.
3. If Accesstrade token is available and verified, system creates tracking links with sub1-sub4 and UTM.
4. System ranks products using money-first scoring.
5. System generates 3-5 Vietnamese Facebook post drafts.
6. System runs mother/baby compliance gate.
7. System sends Telegram approval cards.
8. On approval:
   - If Facebook publish is verified and allowed, publish/schedule.
   - Otherwise create ready-to-post package.
9. System stores product, draft, approval, publish/fallback, and digest records in SQLite.

## 6. Explicit non-goals for Sprint 1

- TikTok.
- YouTube.
- AI video.
- Auto-approve.
- Shopee scraping.
- Multi-page/multi-account.
- Advanced analytics.
- A/B testing.
- Auto-publish without verified token, dry-run, compliance pass, and explicit approval.

## 7. Facebook auto-publish gate

Auto-publish is allowed only if all conditions are true:

```text
approved_by_snail = true
compliance_status = pass
risk_level != high
affiliate_disclosure_present = true
facebook_token_verified = true
page_id_verified = true
publish_dry_run_passed = true
duplicate_post_check_passed = true
kill_switch_off = true
```

If any condition fails, the system must not publish. It must produce a ready-to-post package and notify Snail.

## 8. Secret handling

Tokens and secrets must never be pasted into chat, committed to git, written into docs, or stored in memory.

Expected secret file:

```text
/home/snail/.openclaw/workspace/secrets/affilipilot.env
```

Expected permissions:

```text
chmod 600 /home/snail/.openclaw/workspace/secrets/affilipilot.env
```

Expected variables later:

```env
ACCESSTRADE_TOKEN=...
FACEBOOK_PAGE_ID=...
FACEBOOK_PAGE_ACCESS_TOKEN=...
9ROUTER_API_KEY=...
9ROUTER_API_ENDPOINT=http://100.103.10.31:20128/v1
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Docs and logs should only reference the variable names, never raw values.

## 9. Definition of Done — Sprint 0

Sprint 0 is done when:

- `scripts/verify_all.sh` passes.
- Compliance policy exists and covers mother/baby restricted claims.
- Tracking strategy exists and defines sub1-sub4.
- Product input example exists.
- Product scoring and compliance tests pass.
- No secrets are required.

## 10. Definition of Done — Sprint 1

Sprint 1 is done when:

- A 20-50 link batch can be accepted from Telegram/file.
- 3-5 candidate posts are generated.
- Each post has affiliate disclosure.
- Compliance checker catches restricted mother/baby claims.
- Telegram approval cards can be rendered.
- Approved posts become ready-to-post packages or publish through verified Facebook API.
- Daily digest is generated.
- LLM spend remains within 20k-30k/day cap.

## 11. Success metric

The first business metric is not revenue. It is evidence velocity:

```text
Can Snail produce and approve 3-5 safe affiliate posts/day in under 10 minutes/day?
```

The second metric is traffic:

```text
Can these posts generate measurable clicks via Accesstrade sub_id tracking?
```

Revenue/conversion optimization comes after click tracking works.
