# Media Pipeline

AffiliPilot supports media from user-provided product metadata while waiting for Accesstrade campaign approval.

## Supported input fields

```text
image_url=https://...
image_path=/local/path/product.jpg
video_url=https://...
video_path=/local/path/video.mp4
```

Current implemented fetch/validation is for images:

- PNG
- JPEG
- WEBP
- max 8MB

## Batch behavior

During `run-day` / `create-batch`, AffiliPilot:

1. Reads `image_path` or `image_url` from product metadata.
2. Validates/fetches image.
3. Stores local media under:

```text
<draft_out_dir>/media/<post_id>/
```

4. Adds media status to manifest:

```json
{
  "media": {
    "ok": true,
    "local_path": "...",
    "media_type": "png",
    "reasons": []
  }
}
```

## Facebook planning

If media is present and gates pass, `facebook-plan` now prepares a photo endpoint dry-run:

```text
/PAGE_ID/photos
```

instead of plain feed text:

```text
/PAGE_ID/feed
```

Real photo upload/publish is still not enabled until a separate guarded implementation step.
