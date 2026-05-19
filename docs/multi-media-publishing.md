# Multi-media publishing

AffiliPilot supports collecting multiple product images and video URLs when a marketplace page exposes them.

## Current behavior

- Discovery extracts multiple image URLs from product cards/detail snippets.
- Discovery extracts video URLs from `<video>` and `<source>` tags when present.
- `image_urls` and `video_urls` are persisted through conversion, multi-source selection, and approval batch manifests.
- Media prep downloads gallery images and keeps only images that pass the media quality gate.
- Facebook plan chooses:
  - `multi_photo` when at least 2 local gallery images are available.
  - `single_photo` when only 1 local image is available.
  - `feed` when no image is available, subject to gates.

## Safety

Real publish still requires:

1. approval card delivered with receipt,
2. operator approval,
3. Facebook dry-run plan publishable,
4. `publish-safe` PASS,
5. explicit final publish confirmation.

## Video note

Video URLs are currently collected and shown in manifests, but video publishing is not auto-enabled yet. Facebook video publishing uses a separate endpoint and needs a local video asset plus extra validation. The safe next step is adding video download/probe and a `video_first` strategy after Graph API smoke testing.
