# Bài viết ngắn — GPU FinOps tại NimbusAI

## 1. Chi phí trước và sau tối ưu

Tôi dùng dữ liệu tổng hợp seed 25 để đo chi phí trên sản lượng input + output token. Inference phục vụ 2,400 request và 7,533,027 token/ngày. Baseline chạy tất cả trên large, không cache/batch, tốn $48.87/ngày hay $6.488/1M-token. Sau cascade, cache có phí ghi và batch, chi phí còn $8.61/ngày, $1.143/1M-token, giảm 82.4%. Đơn vị $/token phản ánh throughput hữu ích, trong khi $/GPU-giờ chỉ phản ánh giá thuê.

Kịch bản tổng M5 giảm từ $27,133 xuống $14,630/30 ngày, tiết kiệm $12,503, tương đương 46.1%. Đây là forecast minh họa theo quy ước lab. Training không có token đầu ra để quy đổi tổng M5 thành $/1M-token; cần đối soát resource để tránh trùng savings purchasing/right-sizing/idle.

## 2. Đòn bẩy hiệu quả nhất

Purchasing đóng góp lớn nhất: $10,040/tháng, 80.3% tổng savings. M3 giảm $25,667 xuống $15,627 (39.1%) nhờ spot cho job interruptible và reserved cho inference ổn định. Spot đã tính 5,5% overhead checkpoint/rework. Reserved cần nhu cầu ổn định đủ lâu; không thể suy ra cam kết ba năm an toàn từ một ngày telemetry.

Inference tiết kiệm $1,208/tháng; right-sizing tiềm năng $655; tắt idle $600. Trong inference, cascade có tác động lớn nhất ($37.399/ngày), vì đa số request được route sang small. Phân rã cache/batch phụ thuộc thứ tự áp dụng, nên tôi dùng cùng thứ tự cascade→cache→batch để tránh cộng lặp chiết khấu.

## 3. GPU-Util lie và tác động tài chính

GPU-Util là tỷ lệ thời gian kernel hoạt động, không phải tỷ lệ FLOPs hữu ích. Kernel chờ bộ nhớ hoặc chỉ dùng ít tensor core vẫn có thể làm GPU-Util cao. MFU = achieved/peak FLOPs và MBU = achieved/peak bandwidth giúp thấy hiệu quả thực. gpu-h100-4: Util 98.2%, MFU 0.194; gpu-a10g-1: Util 96.9%, MFU 0.268. Hai GPU này cần profiling trước khi hạ cấu hình; MFU thấp chưa chứng minh nguyên nhân cụ thể hoặc khả năng giữ nguyên hiệu năng trên GPU rẻ hơn.

M5 mô phỏng H100→A100 và A10G→L4, tiết kiệm $655/tháng. Ngoài ra gpu-h100-5 idle 8 giờ/ngày làm mất $20/ngày. Tôi kiểm tra VRAM, bandwidth, tok/s và p95 latency trước right-sizing, đồng thời dùng TTL/lịch tắt để chấm dứt tiền thuê khi GPU không tạo giá trị.

## 4. Ba phần mở rộng đã thực hiện

**Cache (#3):** thêm `cache_is_worth_it()` và phí ghi 1,25×, đọc 0,10× giá input. Ngưỡng đọc lại là n>0.277778. Reuse quy đổi theo token ước lượng của small/large là 2.648/2.594, nên cả hai bật cache. Giữ cascade/batch cố định, bill $9.658588 → $8.609738/ngày (giảm 10.86%). Dataset không có prompt ID/avg_cache_reads; ước lượng dựa trên cacheable fraction của generator, cần log thực để xác nhận.

**Reasoning (#4):** 201 request (8.375% traffic) chiếm 16.23% USD nhưng 94.04% Wh. 80× Wh là giả định mô hình áp sau output 6× của generator, không phải phép đo GPU. Trần 10% không thay đổi gì vì traffic hiện thấp hơn trần. Trần 5% mô phỏng reroute 81 request, tiết kiệm $0.967152/ngày và 14.261 kWh/ngày (45.02% năng lượng). Rule đề xuất: standard trước, reasoning khi confidence đã hiệu chuẩn <0,70 hoặc task phức tạp đã được xác nhận; cần đánh giá chất lượng vì output và mẫu số token đều giảm.

**Carbon (#5):** tính đủ năm job interruptible, so sánh năm vùng theo điện và carbon. Theo số ngày trong CSV, tổng 1,887.395 kWh gồm overhead spot. Chuyển sang europe-north1 giảm 660.588 kgCO2e và $56.622 tiền điện. us-east-wa rẻ nhất và thắng điểm cân bằng 50/50, giảm $122.681 và 547.345 kgCO2e. Training là ứng viên chuyển vùng trước; kiểm tra egress, deadline và vị trí dữ liệu. Tiền điện thường nằm trong thuê cloud, nên không cộng khoản này hoặc kịch bản reasoning vào M5.

## 5. Ba khuyến nghị đầu tiên

1. **Tối ưu purchasing:** chuyển job phù hợp sang spot có checkpoint; chỉ reserved cho nhu cầu được dự báo ổn định, sau khi đối soát giá, utilization và kỳ cam kết.
2. **Tối ưu inference có quality gate:** cascade trước, cache khi vượt break-even và log writes/TTL, batch eval; quản lý reasoning bằng cả ngân sách USD và Wh, kiểm tra SLA trước khi áp quota.
3. **Thiết lập trách nhiệm vận hành:** showback theo team/project, bổ sung tags (coverage hiện 91.8%), tự động tắt idle, benchmark right-sizing; thử chuyển training tới vùng phù hợp mục tiêu tiền điện/carbon và theo dõi savings thực hiện hàng tuần.

_Bài viết được M5 tạo từ cùng số liệu với report.md; xem report và mission_results.json để đối soát._
