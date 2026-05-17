# Compliance Policy — Mother/Baby Affiliate Content

## Principle

The page is in a sensitive mother/baby niche. AffiliPilot must avoid medical, health, child-development, and fake-experience claims.

## Allowed Sprint 1 product zones

- Household utility products for parents.
- Organization/storage for baby items.
- Simple feeding accessories without health claims.
- Educational toys with modest wording.
- Stroller accessories.
- Baby-room lights and non-medical accessories.
- Home safety accessories such as corner guards, cabinet locks, and mats.

## Blocked or high-risk zones for Sprint 1

- Milk/formula.
- Medicine.
- Supplements/vitamins.
- Fever/cough/runny-nose treatment.
- Rash treatment or skin disease treatment.
- Height growth claims.
- Brain development/intelligence claims.
- Medical devices.
- Weight-loss products for mothers.
- Strong cosmetic claims.
- Products with unclear origin or fake-brand risk.

## Forbidden claim patterns

Do not publish drafts containing claims like:

- chữa khỏi / trị khỏi / điều trị
- hết ho / hết sốt / hết hăm
- tăng chiều cao
- phát triển trí não vượt trội
- tăng đề kháng
- an toàn tuyệt đối
- tốt nhất / số 1 without evidence
- chính hãng 100% without source evidence
- mẹ nào cũng cần / bắt buộc phải có
- mình đã dùng rồi if Snail did not verify real usage

## Required disclosure

Each affiliate post must include a clear disclosure, for example:

```text
Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ mà không làm thay đổi giá mua của bạn.
#tiepthilienket #ShopeeAffiliate
```

## Safe wording examples

Prefer:

- “mẹ có thể tham khảo”
- “phù hợp nếu nhà cần...”
- “giúp sắp xếp gọn hơn”
- “tiện cho...”
- “giá/ưu đãi có thể thay đổi theo thời điểm”

Avoid:

- “cam kết”
- “chắc chắn”
- “trị”
- “khỏi”
- “tuyệt đối”

## Gate decision

- `pass`: low-risk product, disclosure present, no forbidden claims.
- `needs_review`: mild risk, unclear source, price/claim needs edit.
- `block`: medical/health claim, missing disclosure, fake personal review, high-risk category.
