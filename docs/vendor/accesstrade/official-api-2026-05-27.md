# Tài Liệu Tích Hợp API Accesstrade

## Mục Lục

1. [Xác Thực (Authentication)](#xác-thực)
2. [Danh Sách Campaign](#danh-sách-campaign)
3. [Tạo Tracking Link](#tạo-tracking-link)
4. [Tỷ Lệ Hoa Hồng Campaign](#tỷ-lệ-hoa-hồng)
5. [Danh Sách Giao Dịch](#danh-sách-giao-dịch)
6. [Danh Sách Đơn Hàng v2](#danh-sách-đơn-hàng-v2)
7. [Thông Tin Sản Phẩm Đơn Hàng](#thông-tin-sản-phẩm)
8. [Chi Tiết Sản Phẩm](#chi-tiết-sản-phẩm)
9. [Thông Tin Datafeeds](#datafeeds)
10. [Thông Tin Khuyến Mãi](#khuyến-mãi)
11. [Sản Phẩm Bán Chạy](#sản-phẩm-bán-chạy)
12. [Chi Tiết Đơn Hàng](#chi-tiết-đơn-hàng)
13. [Mã Lỗi](#mã-lỗi)

---

## <a id="xác-thực"></a>1. Xác Thực (Authentication)

### Yêu Cầu Chung

Tất cả các request API đều yêu cầu token trong header:

```
Authorization: Token <access_key>
Content-Type: application/json
```

### Lấy Access Key

- Truy cập: `https://pub.accesstrade.vn/publisher_profile/personal_info?position=info`
- Sao chép `access_key` từ trang cá nhân
- Định dạng header: `Token + space + access_key`

**Ví dụ:**
```
Authorization: Token your_access_key_here
```

---

## <a id="danh-sách-campaign"></a>2. Danh Sách Campaign

### Endpoint

```
GET https://api.accesstrade.vn/v1/campaigns
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `approval` | Không | Filter campaign đã duyệt (giá trị: `successful`) |
| `campaign_id` | Không | Lọc theo ID campaign |
| `limit` | Không | Số campaign per page (mặc định: 20) |
| `page` | Không | Trang (mặc định: 1) |

### Ví Dụ Request

```
https://api.accesstrade.vn/v1/campaigns?limit=20&page=25&approval=successful
```

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số campaign |
| `data[].id` | ID campaign |
| `data[].name` | Tên campaign |
| `data[].approval` | Trạng thái: Unregistered, Pending, Successful |
| `data[].status` | 1 = Đang chạy |
| `data[].merchant` | Tên merchant |
| `data[].cookie_duration` | Thời gian cookie (giây) |
| `data[].description` | Mô tả chi tiết campaign |
| `data[].start_time` | Ngày bắt đầu |
| `data[].end_time` | Ngày kết thúc |
| `data[].category` | Danh mục |
| `data[].url` | URL campaign |

### Mã Trạng Thái Approval

- **Unregistered**: Chưa đăng ký
- **Pending**: Đang chờ duyệt
- **Successful**: Đã duyệt thành công

---

## <a id="tạo-tracking-link"></a>3. Tạo Tracking Link

### Endpoint

```
POST https://api.accesstrade.vn/v1/product_link/create
```

### Request Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `campaign_id` | **Có** | ID campaign |
| `urls` | Không | Danh sách URL cần tạo link |
| `utm_source` | Không | Tham số bổ sung |
| `utm_medium` | Không | Tham số bổ sung |
| `utm_campaign` | Không | Tham số bổ sung |
| `utm_content` | Không | Tham số bổ sung |
| `sub1`, `sub2`, `sub3`, `sub4` | Không | Tham số tùy chỉnh |
| `url_enc` | Không | Mã hóa URL (boolean) |

### Ví Dụ CURL

```bash
curl --location 'https://api.accesstrade.vn/v1/product_link/create' \
--header 'Content-Type: application/json' \
--header 'Authorization: token {your_token}' \
--data '{
    "campaign_id": "4348614231480407268",
    "urls": ["https://shopee.vn/m/ma-giam-gia"],
    "utm_source": "test_source",
    "url_enc": true,
    "utm_medium": "test_medium",
    "utm_campaign": "test_campaign",
    "utm_content": "test_content",
    "sub1": "test_sub1"
}'
```

### Response

```json
{
    "data": {
        "error_link": [],
        "success_link": [
            {
                "aff_link": "https://tracking.dev.accesstrade.me/deep_link/...",
                "short_link": "https://shorten.dev.accesstrade.me/ujrBHxpc",
                "url_origin": "https://shopee.vn"
            }
        ],
        "suspend_url": []
    },
    "success": true
}
```

---

## <a id="tỷ-lệ-hoa-hồng"></a>4. Tỷ Lệ Hoa Hồng Campaign

### Endpoint

```
GET https://api.accesstrade.vn/v1/commission_policies
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `camp_id` | **Có** | ID campaign |
| `month` | Không | Tháng áp dụng (MM-YYYY, ví dụ: 01-2021) |

### Ví Dụ

```
https://api.accesstrade.vn/v1/commission_policies?camp_id=5338806296999499238&month=01-2021
```

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `category[]` | Danh sách hoa hồng theo danh mục |
| `category[].category_id` | ID danh mục |
| `category[].sales_price` | Giá hoa hồng cố định |
| `category[].sales_ratio` | Tỷ lệ hoa hồng (%) |
| `category[].taget_month` | Tháng áp dụng |
| `product[]` | Danh sách hoa hồng theo sản phẩm |
| `default[]` | Hoa hồng mặc định |
| `default[].result_id` | Loại hoa hồng: 1=Cố định, 3=Theo sản phẩm, 30=Theo danh mục |
| `default[].reward_type` | Phương thức: 1=Giá cố định, 2=Tỷ lệ theo giá đơn |

---

## <a id="danh-sách-giao-dịch"></a>5. Danh Sách Giao Dịch

### Endpoint

```
GET https://api.accesstrade.vn/v1/transactions
```

### Giới Hạn

- **Rate Limit**: 10 requests / 1 phút

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `since` | **Có** | Thời gian bắt đầu (ISO format: 2019-08-01T00:00:00Z) |
| `until` | **Có** | Thời gian kết thúc |
| `page` | Không | Trang (mặc định: 1) |
| `offset` | Không | Offset (mặc định: 0) |
| `limit` | Không | Số item/page (mặc định: 100) |
| `merchant` | Không | Tên merchant (ví dụ: tikivn) |
| `utm_source` | Không | (ví dụ: facebook) |
| `utm_campaign` | Không | |
| `utm_medium` | Không | (ví dụ: email) |
| `utm_content` | Không | |
| `status` | Không | 0=Hold, 1=Approved, 2=Rejected |
| `is_confirmed` | Không | 0=Unapproved, 1=Approved |
| `transaction_id` | Không | Mã giao dịch (có thể nhiều, phân cách dấu phẩy) |
| `update_time_start` | Không | Thời gian cập nhật bắt đầu |
| `update_time_end` | Không | Thời gian cập nhật kết thúc |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số giao dịch |
| `data[].merchant` | Tên merchant |
| `data[].status` | Trạng thái: 0=Hold, 1=Approved, 2=Rejected |
| `data[].transaction_id` | ID giao dịch |
| `data[].transaction_time` | Thời gian giao dịch |
| `data[].click_time` | Thời gian click |
| `data[].update_time` | Thời gian cập nhật |
| `data[].confirmed_time` | Thời gian duyệt |
| `data[].is_confirmed` | 0=Chưa duyệt, 1=Đã duyệt |
| `data[].transaction_value` | Giá trị giao dịch |
| `data[].commission` | Hoa hồng |
| `data[].product_id` | ID sản phẩm |
| `data[].product_price` | Giá sản phẩm |
| `data[].product_quantity` | Số lượng sản phẩm |
| `data[].product_name` | Tên sản phẩm |
| `data[].category_name` | Tên danh mục |
| `data[].conversion_id` | ID conversion |
| `data[].conversion_platform` | Nền tảng conversion |
| `data[].customer_type` | Loại khách |
| `data[].reason_rejected` | Lý do từ chối |
| `data[]._extra` | Thông tin OS, browser |

---

## <a id="danh-sách-đơn-hàng-v2"></a>6. Danh Sách Đơn Hàng v2

### Endpoint

```
GET https://api.accesstrade.vn/v1/order-list
```

### Giới Hạn

- **Rate Limit**: 10 requests / 1 phút
- **Cache**: 1 phút

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `since` | **Có** | Thời gian bắt đầu (ISO format) |
| `until` | **Có** | Thời gian kết thúc |
| `utm_source` | Không | (ví dụ: facebook) |
| `utm_campaign` | Không | |
| `utm_medium` | Không | (ví dụ: email) |
| `utm_content` | Không | |
| `page` | Không | Trang (mặc định: 1) |
| `limit` | Không | Số đơn/page (mặc định: 30, max: 300) |
| `status` | Không | 0=Hold, 1=Approved, 2=Rejected |
| `merchant` | Không | (ví dụ: adayroi, lazada) |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số đơn |
| `data[].at_product_link` | Link sản phẩm tracking |
| `data[].billing` | Giá trị đơn |
| `data[].browser` | Nền tảng |
| `data[].category_name` | Danh mục |
| `data[].click_time` | Thời gian click |
| `data[].client_platform` | Nền tảng client |
| `data[].confirmed_time` | Thời gian duyệt |
| `data[].is_confirmed` | 0=Chưa duyệt, 1=Đã duyệt |
| `data[].landing_page` | Trang landing |
| `data[].merchant` | Merchant |
| `data[].order_id` | ID đơn |
| `data[].order_pending` | Số đơn chờ duyệt |
| `data[].order_reject` | Số đơn từ chối |
| `data[].order_approved` | Số đơn approved |
| `data[].product_category` | Danh mục sản phẩm |
| `data[].products_count` | Tổng số sản phẩm |
| `data[].pub_commission` | Hoa hồng publisher |
| `data[].sales_time` | Thời gian bán |
| `data[].update_time` | Thời gian cập nhật |
| `data[].website` | Website |

---

## <a id="thông-tin-sản-phẩm"></a>7. Thông Tin Sản Phẩm Đơn Hàng

### Endpoint

```
GET https://api.accesstrade.vn/v1/order-products
```

### Giới Hạn

- **Rate Limit**: 10 requests / 1 phút

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `order_id` | **Có** | ID đơn (từ API order-list) |
| `merchant` | **Có** | Tên merchant |
| `page` | Không | Trang (mặc định: 1) |
| `limit` | Không | Số item/page |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số sản phẩm |
| `data[]._id` | ID sản phẩm |
| `data[].billing` | Giá sản phẩm |
| `data[].billing.approved` | Giá approved |
| `data[].billing.pending` | Giá pending |
| `data[].billing.reject` | Giá reject |
| `data[].campaign_id` | ID campaign |
| `data[].click_time` | Thời gian click |
| `data[].commission` | Hoa hồng |
| `data[].confirmed_time` | Thời gian duyệt |
| `data[].merchant` | Merchant |
| `data[].product_price` | Giá sản phẩm |
| `data[].product_quantity` | Số lượng |
| `data[].quantity` | Số lượng chi tiết |
| `data[].reason_rejected` | Lý do từ chối |
| `data[].sales_time` | Thời gian bán |

---

## <a id="chi-tiết-sản-phẩm"></a>8. Chi Tiết Sản Phẩm

### Endpoint

```
GET https://api.accesstrade.vn/v1/product_detail
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `merchant` | **Có** | (ví dụ: adayroi, lazada) |
| `product_id` | **Có** | ID sản phẩm |

### Ví Dụ

```
https://api.accesstrade.vn/v1/product_detail?merchant=fpt_longchau&product_id=00033675--80799010-N-1
```

### Response

```json
{
    "name": "Tên sản phẩm",
    "price": 1000000.0,
    "short_desc": "Mô tả ngắn",
    "discount": 800000.0,
    "link": "https://...",
    "image": "https://...",
    "desc": "Mô tả đầy đủ",
    "category_id": "...",
    "brand": "...",
    "category_name": "Danh mục"
}
```

---

## <a id="datafeeds"></a>9. Thông Tin Datafeeds

### Endpoint

```
GET https://api.accesstrade.vn/v1/datafeeds
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `campaign` | Không | Merchant sở hữu |
| `domain` | Không | Tên miền |
| `discount_amount_from` | Không | Giảm từ (tiền) |
| `discount_amount_to` | Không | Giảm đến (tiền) |
| `discount_rate_from` | Không | Giảm từ (%) |
| `discount_rate_to` | Không | Giảm đến (%) |
| `page` | Không | Trang (mặc định: 1) |
| `limit` | Không | Số sản phẩm/page (mặc định: 50, max: 200) |
| `price_from` | Không | Giá từ |
| `price_to` | Không | Giá đến |
| `discount_from` | Không | Giá sau giảm từ |
| `discount_to` | Không | Giá sau giảm đến |
| `status_discount` | Không | 0=Không giảm, 1=Có giảm |
| `update_from` | Không | Cập nhật từ (dd-mm-yyyy) |
| `update_to` | Không | Cập nhật đến |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `data[].aff_link` | Deep link |
| `data[].campaign` | Campaign |
| `data[].cate` | Danh mục |
| `data[].desc` | Mô tả |
| `data[].discount` | Giá sau giảm |
| `data[].discount_amount` | Tiền giảm |
| `data[].discount_rate` | Tỷ lệ giảm (%) |
| `data[].domain` | Tên miền |
| `data[].image` | Hình ảnh |
| `data[].name` | Tên sản phẩm |
| `data[].price` | Giá gốc |
| `data[].product_id` | ID sản phẩm |
| `data[].sku` | Mã SKU |
| `data[].status_discount` | Trạng thái giảm |
| `data[].update_time` | Thời gian cập nhật |
| `data[].url` | Link sản phẩm |

---

## <a id="khuyến-mãi"></a>10. Thông Tin Khuyến Mãi

### Endpoint

```
GET https://api.accesstrade.vn/v1/offers_informations
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `scope` | Không | "expiring" để lấy khuyến mãi sắp hết, không chỉ định = all |
| `merchant` | Không | Tên merchant |
| `categories` | Không | Danh mục (phân cách dấu phẩy) |
| `domain` | Không | Tên miền (ví dụ: lazada.vn) |
| `coupon` | Không | 1=Có mã, 0=Không mã, không chỉ định = all |
| `status` | Không | 1=Đang hoạt động, 0=Hết hạn, không chỉ định = all |
| `limit` | Không | Số khuyến mãi/page |
| `page` | Không | Trang |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `data[].id` | ID khuyến mãi |
| `data[].name` | Tên khuyến mãi |
| `data[].merchant` | Merchant |
| `data[].link` | Link khuyến mãi |
| `data[].aff_link` | Affiliate link |
| `data[].image` | Hình ảnh |
| `data[].content` | Nội dung chi tiết |
| `data[].start_time` | Thời gian bắt đầu |
| `data[].end_time` | Thời gian kết thúc |
| `data[].domain` | Tên miền |
| `data[].categories` | Danh sách danh mục |
| `data[].banners` | Danh sách banner |
| `data[].coupons` | Danh sách mã |

---

## <a id="sản-phẩm-bán-chạy"></a>11. Sản Phẩm Bán Chạy

### Endpoint

```
GET https://api.accesstrade.vn/v1/top_products
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `date_from` | Không | Ngày bắt đầu (dd-mm-yyyy) |
| `date_to` | Không | Ngày kết thúc |
| `merchant` | Không | Merchant (ví dụ: lazada) |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số sản phẩm |
| `data[].product_id` | ID sản phẩm |
| `data[].name` | Tên sản phẩm |
| `data[].category_name` | Danh mục |
| `data[].category_id` | ID danh mục |
| `data[].price` | Giá gốc |
| `data[].discount` | Giá giảm |
| `data[].image` | Hình ảnh |
| `data[].link` | Link sản phẩm |
| `data[].aff_link` | Affiliate link |
| `data[].desc` | Mô tả |
| `data[].brand` | Thương hiệu |
| `data[].total` | Tổng bán |

---

## <a id="chi-tiết-đơn-hàng"></a>12. Chi Tiết Đơn Hàng

### Endpoint

```
GET https://api.accesstrade.vn/v1/orders_detail
```

### Query Parameters

| Param | Bắt Buộc | Mô Tả |
|-------|---------|-------|
| `order_id` | **Có** | ID đơn |
| `merchant` | **Có** | Tên merchant |
| `page` | Không | Trang (mặc định: 1) |
| `limit` | Không | Số item/page (mặc định: 30, max: 300) |

### Response Fields

| Field | Mô Tả |
|-------|-------|
| `total` | Tổng số chi tiết |
| `data[].product_id` | ID sản phẩm |
| `data[].amount` | Giá trị |
| `data[].campaign_id` | ID campaign |
| `data[].click_time` | Thời gian click |
| `data[].confirmed_time` | Thời gian duyệt |
| `data[].product_price` | Giá sản phẩm |
| `data[].product_quantity` | Số lượng |
| `data[].pub_commission` | Hoa hồng publisher |
| `data[].reason_rejected` | Lý do từ chối |
| `data[].sales_time` | Thời gian bán |
| `data[].status` | Trạng thái |
| `data[]._extra` | Thông tin OS, browser |

---

## <a id="mã-lỗi"></a>13. Mã Lỗi

| Mã | Ý Nghĩa |
|----|---------|
| **400** | Bad Request – Request không hợp lệ |
| **401** | Unauthorized – API key sai |
| **403** | Forbidden – Yêu cầu được giới hạn cho admin |
| **404** | Not Found – API không tìm thấy |
| **405** | Method Not Allowed – Method không hợp lệ |

---

## Thực Hành Tốt Nhất

### 1. Rate Limiting

- Một số API có giới hạn 10 requests/phút
- Hãy lưu cache dữ liệu khi có thể
- Tắc cache 1 phút cho dữ liệu order-list

### 2. Format ISO 8601

- Sử dụng format: `YYYY-MM-DDTHH:MM:SSZ`
- Ví dụ: `2021-08-01T00:00:00Z`

### 3. Pagination

- Sử dụng tham số `page` và `limit`
- Mặc định limit là 30-100 tùy API
- Max limit thường là 300

### 4. Xử Lý Lỗi

- Kiểm tra `success` field trong response
- Đọc chi tiết từ HTTP status code
- Retry với backoff exponential để tránh rate limit

### 5. Authorization

- Luôn gửi header `Authorization` đúng định dạng
- Bảo mật access key
- Regenerate nếu access key bị lộ

---

## Quy Trình Tích Hợp Điển Hình

1. **Xác Thực** → Lấy access key từ dashboard
2. **Lấy Campaigns** → Tìm campaign muốn promote
3. **Tạo Tracking Links** → Sinh link theo campaign
4. **Theo Dõi Clicks** → Sử dụng API danh sách giao dịch
5. **Kiểm Tra Orders** → Lấy danh sách đơn hàng
6. **Tính Hoa Hồng** → Sử dụng commission_policies
7. **Báo Cáo** → Phân tích data và lập báo cáo

---

## Tài Liệu Tham Khảo

- **Trang Chính**: https://developers.accesstrade.vn/
- **Cổng Thông Tin Publisher**: https://pub.accesstrade.vn/
- **Lấy Access Key**: https://pub.accesstrade.vn/publisher_profile/personal_info?position=info

---

*Tài liệu này được cập nhật lần cuối: 27/05/2026*
