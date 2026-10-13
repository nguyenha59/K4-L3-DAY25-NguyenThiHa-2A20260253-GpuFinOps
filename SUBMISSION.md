# Hoàn thành Lab 25 — GPU FinOps

Đã triển khai Your Turn **#3 Cache**, **#4 Reasoning**, **#5 Carbon-aware scheduling**.
Mọi phân tích và bài viết ngắn được sinh từ code, cùng dữ liệu seed 25.

## File nộp

- [Báo cáo kỹ thuật](outputs/report.md)
- [Biểu đồ waterfall](outputs/savings.png)
- [FOCUS export — toàn bộ request](outputs/focus_export.csv)
- [Bài viết ngắn trả lời 5 câu](outputs/writeup.md)
- [Số liệu chi tiết để đối soát](outputs/mission_results.json)

Nộp kèm mã nguồn trong repo để giảng viên chạy và đánh giá các extension.

## Chạy và kiểm tra

```powershell
python data/generate.py
python missions/run_all.py
python missions/m6_carbon_scheduling.py
python verify.py
pytest -q
python validation/check_extensions.py
```

`verify.py` và M5 tạo lại toàn bộ file nộp. `tests/` giữ nguyên; kiểm tra mới nằm trong `validation/`.
Không cần cloud, GPU, API key hoặc phần bonus.

## Mã nguồn chính

- Cache: `finops/pricing.py`, `finops/cache_economics.py`, tích hợp M2/M4.
- Reasoning: `finops/reasoning.py`, tích hợp M2/M5; so sánh cap 10% và 5%.
- Carbon: `finops/carbon_schedule.py`, `missions/m6_carbon_scheduling.py`;
  so sánh đủ 5 vùng, tách training và sandbox/eval, kỳ chạy CSV và 30 ngày.
- Báo cáo/bài viết: `finops/report.py`, `finops/narrative.py`, `missions/m5_report.py`.

Phí ghi cache được mô hình hóa thêm nên chi phí optimized thay đổi so với code gốc.
Reuse cache là ước lượng quy đổi theo token vì CSV không có prompt ID/avg_cache_reads.
Reasoning và carbon là kịch bản mô phỏng năng lượng; xem giả định và giới hạn trong báo cáo.
