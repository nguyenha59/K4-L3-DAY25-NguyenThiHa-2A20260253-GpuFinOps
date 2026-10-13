# NimbusAI — GPU Cost Optimization Report

**Period:** 30-day recurring lab scenario

**Baseline spend:** $27,133

**Optimized spend:** $14,630

**Projected savings:** $12,503  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,208 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cleanest region: europe-north1
- Cheapest electricity region: us-east-wa
- Electricity per query (us-east-1): $0.00002880

## Phạm vi và phương pháp tính

Dữ liệu tổng hợp seed 25, snapshot minh họa tháng 6/2026; không cần GPU, cloud hoặc API key. M1 dùng 264 mẫu giờ của 11 GPU; M2/M4 dùng 2.400 request trong một ngày; M3 có 8 workload. Nguồn: `data/generate.py`, bốn CSV trong `data/`, và các hàm `finops/`.

M5 giữ quy ước lab: một tháng = 30 ngày; dùng chi phí M2 làm tròn cent/ngày, chi phí M3 làm tròn USD/tháng, rồi làm tròn từng lever sang USD. Bảng M2 bên dưới giữ sáu chữ số thập phân để đối soát; chênh lệch nhỏ là do làm tròn.

`$/1M-token = tổng USD / ((input_tokens + output_tokens)/1.000.000)`. Input đã cache vẫn nằm trong sản lượng token phục vụ; ba lever M2 dùng cùng mẫu số. Không quy đổi tổng hóa đơn M5 sang $/token vì workloads training chưa có số token đầu ra.

Tổng M5 là kịch bản cộng bốn lever của lab. Telemetry và workloads chưa có liên kết resource/job để xác minh right-sizing/idle có trùng với tài nguyên được giảm giá purchasing hay không. Cần đối soát ở cấp resource và tính lại giá sau mỗi thay đổi trước khi xem đây là tiết kiệm đã thực hiện. M3 giả lập recurring 30 ngày cho mọi job và tính reserved theo giờ sử dụng; hợp đồng reserved thực tế có thể tính cả giờ không dùng. Không cam kết ba năm chỉ từ dữ liệu này.

## M1 — Hiệu quả GPU và GPU-Util lie

| GPU | Loại | GPU-Util (%) | MFU | MBU | Giờ idle/ngày |
|---|---|---:|---:|---:|---:|
| gpu-h100-0 | H100 | 94.4 | 0.417 | 0.446 | 0 |
| gpu-h100-1 | H100 | 95.2 | 0.408 | 0.440 | 0 |
| gpu-h100-2 | H100 | 94.3 | 0.401 | 0.423 | 0 |
| gpu-h100-3 | H100 | 93.1 | 0.427 | 0.444 | 0 |
| gpu-h100-4 | H100 | 98.2 | 0.194 | 0.207 | 0 |
| gpu-h100-5 | H100 | 61.1 | 0.261 | 0.271 | 8 |
| gpu-a100-0 | A100 | 31.4 | 0.259 | 0.276 | 0 |
| gpu-a100-1 | A100 | 28.0 | 0.236 | 0.247 | 0 |
| gpu-a10g-0 | A10G | 25.0 | 0.219 | 0.235 | 0 |
| gpu-a10g-1 | A10G | 96.9 | 0.268 | 0.302 | 0 |
| gpu-l4-0 | L4 | 40.0 | 0.302 | 0.328 | 0 |

GPU-Util cao nhất: **gpu-h100-4**, 98.2%, nhưng MFU chỉ 0.194. Các GPU bị gắn cờ: `gpu-h100-4`, `gpu-a10g-1`.

GPU-Util đo tỷ lệ thời gian GPU có kernel hoạt động trong cửa sổ lấy mẫu; MFU đo achieved TFLOPs/peak TFLOPs. Kernel có thể hoạt động nhưng chờ bộ nhớ, phụ thuộc dữ liệu hoặc dùng ít tensor core; kernel nhỏ và overhead điều phối cũng làm throughput thấp. Vì vậy GPU-Util cao chưa chứng minh GPU tạo nhiều FLOPs hữu ích. Đây là các nguyên nhân cần profile, chưa phải chẩn đoán nguyên nhân từ telemetry. Với decode, xem thêm MBU; MBU thấp một mình chưa đủ kết luận memory-bound. Roofline so arithmetic intensity với ridge point: decode 1–2 FLOP/byte thấp hơn ~295 trên H100, còn prefill ~455 cao hơn ngưỡng này.

| GPU gắn cờ | Đề xuất trong M5 | Giảm $/GPU-giờ | Tiềm năng USD/30 ngày |
|---|---|---:|---:|
| gpu-h100-4 | H100 → A100 | $0.71 | $511.20 |
| gpu-a10g-1 | A10G → L4 | $0.20 | $144.00 |

Hạ GPU trong M5 là giả thuyết tiết kiệm: phải kiểm tra VRAM, bandwidth, tok/s và latency trước. Đặc biệt H100→A100 giảm peak TFLOPs, A10G→L4 giảm peak bandwidth; không thể khẳng định cùng hiệu năng chỉ từ MFU thấp.

Idle tại `gpu-h100-5`: 8 giờ × $2,50 = **$20.00/ngày**, hay **$600/tháng**, chiếm 2.21% baseline M5. Dùng TTL cho sandbox, lịch tắt qua đêm và kiểm tra job/queue trước khi scale-to-zero.

## M2 — Baseline/optimized theo $/1M-token

2,400 request; **7,533,027 input + output tokens/ngày**. Baseline $48.87/ngày → $8.61/ngày; **$6.488 → $1.143/1M-token**, tiết kiệm **82.4%**.

| Bước áp dụng tuần tự | USD/ngày | $/1M-token | Savings thêm USD/ngày |
|---|---:|---:|---:|
| Baseline: large, no cache/batch | $48.874161 | $6.488 | $0.000000 |
| Cascade | $11.475643 | $1.523 | $37.398518 |
| Cache (gate + write premium) | $10.406786 | $1.381 | $1.068856 |
| Batch | $8.609738 | $1.143 | $1.797048 |

Cascade đóng góp lớn nhất trong inference: $37.398518/ngày (~92.9% tổng savings M2). Đây là attribution theo thứ tự cascade→cache→batch; đổi thứ tự sẽ đổi phần đóng góp do tương tác chiết khấu. Small có giá input/output $0,20/$0,40 mỗi triệu token so với large $3/$15. Chỉ route request phù hợp chất lượng sang small. Batch dành cho eval hoặc tác vụ không cần trả lời real-time; không áp dụng mặc định cho chat cần latency thấp.

`discount_stack(batch=True, cache_hit_frac=1)=0,5×0,1=0,05`: 95% off chỉ cho phần input lý tưởng đã cache 100%, chưa tính output, phí ghi và lưu trữ. Không dùng 95% này thay cho mức tiết kiệm thực tế toàn bộ request.

## M3 — Purchasing theo workload

On-demand **$25,667/tháng** → spot/reserved **$15,627/tháng**, tiết kiệm **39.1%**. Ngưỡng minh họa reserved discount 45%: duty cycle ≥55% (=13,2 giờ/ngày). Giá catalog từng GPU có discount khác nhau; policy M3 dùng ngưỡng chung, nên cần tính lại ngưỡng và điều khoản cụ thể trước khi commit.

| Job | GPU | Tier | On-demand USD/tháng | Optimized USD/tháng |
|---|---|---|---:|---:|
| job-train-llm | H100 | spot | $12,000 | $7,596 |
| job-train-embed | A100 | spot | $2,148 | $1,393 |
| job-finetune | H100 | spot | $900 | $570 |
| job-infer-chat | A10G | reserved | $4,320 | $2,592 |
| job-infer-rag | A100 | reserved | $3,866 | $2,160 |
| job-infer-search | L4 | reserved | $1,728 | $972 |
| job-dev-sandbox | A10G | spot | $480 | $203 |
| job-batch-eval | H100 | spot | $225 | $142 |

Các job interruptible dưới 24 giờ/ngày dùng spot; ba workload inference ổn định dùng reserved. Checkpoint simulation tính effective GPU-hours = useful GPU-hours × (1+0,03+0,05×0,5)=1,055×: 3% checkpoint cộng rework kỳ vọng 2,5%. Giờ thực trả cao hơn giờ hữu ích, nhưng giá spot vẫn giúp tổng tiền giảm. Giữ on-demand cho burst/nhu cầu chưa dự báo được; reserved chỉ cho nhu cầu ổn định đủ dài.

## M4 — Showback, chargeback và FOCUS

| Team | USD/ngày | Tỷ trọng chi phí |
|---|---:|---:|
| assistant | $2.662508 | 30.92% |
| search | $2.501091 | 29.05% |
| eval | $1.797048 | 20.87% |
| rag | $1.649091 | 19.15% |

Team **assistant** chi nhiều nhất (30.92%). Tag `team` + `project` đầy đủ: 2203/2400 = 91.8% (làm tròn ~92%); vượt gate 80%, chargeback ready = **True** theo tiêu chí lab. Coverage cao giúp tránh phân bổ phần lớn hóa đơn bằng phỏng đoán; vẫn cần xác nhận owner cho project chưa gắn tag, thống nhất ngân sách và xử lý chi phí dùng chung.

`focus_export.csv` xuất **2,400 request**, mỗi request có ResourceId riêng; tổng BilledCost ≈ **$8.609738/ngày**, cùng chính sách cache-write như M2. Giữ 12 chữ số thập phân khi xuất để đối soát request nhỏ. Đây là schema FOCUS-style tối giản của lab, giúp chuẩn hóa tiền tệ, kỳ tính phí và tags giữa nhà cung cấp; chưa phải bộ dữ liệu chứng nhận đầy đủ FOCUS.

## Your Turn #3 — Kinh tế cache

Code: `pricing.cache_is_worth_it()` và `cache_economics.analyze_cache()`; được áp dụng trước khi tính cache savings trong M2/M4. Đặt `write_cost=1,25` là tổng giá ghi so với input thường, `read_discount=0,10` là phần giá còn lại khi đọc. Với một lần ghi và n lần đọc lại: không cache trả (1+n)P, cache trả (1,25+0,10n)P. Chỉ cache khi `n > (1,25−1)/(1−0,10)=0,277778`; bằng ngưỡng chưa tạo savings. Một lần đọc lại nguyên prefix đã vượt ngưỡng; n trung bình có thể là số thập phân.

Dataset không có `avg_cache_reads`, prompt ID, cache-write event hoặc TTL. Ước lượng write-equivalent tokens = cacheable input − cached input, với cacheable fraction từ generator: assistant/rag 70%, team khác 10%. Reuse = cached read tokens/write-equivalent tokens; gate dùng tỷ lệ có trọng số batch. Đây là tỷ lệ tái dùng quy đổi theo token, không phải số lần đọc prefix đã quan sát. Hàm cũng hỗ trợ `avg_cache_reads` do caller cung cấp; dữ liệu thực cần log prefix/TTL để kiểm định.

| Tier | Giá input/ghi/đọc USD/1M | Ngưỡng n | Reuse ước lượng | Reuse trọng số batch | Gate | Net savings USD/ngày* |
|---|---:|---:|---:|---:|---|---:|
| small | 0.20/0.25/0.02 | 0.277778 | 2.648240 | 2.649841 | Bật | $0.213488 |
| large | 3.00/3.75/0.30 | 0.277778 | 2.593757 | 2.595566 | Bật | $0.835362 |

*Giữ cascade và batch cố định: không cache $9.658588 → cache có phí ghi $8.609738/ngày, net saving $1.048850 (10.86%). Khác attribution M2 vì ở đây batch đã bật trước khi so cache.

Phí ghi thêm **$0.125115/ngày**. Kết quả gốc coi ghi miễn phí: $8.484623/ngày; kết quả mới: $8.609738/ngày. Hai tier cùng ngưỡng vì dùng cùng hệ số giá; large tiết kiệm USD nhiều hơn vì giá input cao hơn. Hệ số ghi 1,25 là giả định bổ sung của bài, chưa tính phí storage/TTL.

| Sensitivity n | Gate | Savings theo đơn vị giá input P |
|---:|---|---:|
| 0.138889 (below) | Tắt | -0.125000 |
| 0.277778 (equal) | Tắt | 0.000000 |
| 1.277778 (above) | Bật | 0.900000 |

## Your Turn #4 — Ngân sách reasoning

Code: `finops/reasoning.py`, được M2/M5 gọi. Giá USD dùng chính policy M2; năng lượng dùng `wh_per_query` = 0,30 Wh/1.000 token, nhân 80 khi reasoning. Đây là mô hình năng lượng, không phải watt đo từ GPU. Generator đã tăng output reasoning 6×; hệ số 80 áp lên số token đó nên không thể nói mọi reasoning request chỉ tốn đúng 80× so với câu trả lời thường có số token khác. Giữ nguyên cùng số token thì tỷ số Wh mới đúng 80×.

| Traffic | Request | % traffic | USD/ngày | % chi phí | Wh/ngày | % năng lượng |
|---|---:|---:|---:|---:|---:|---:|
| reasoning | 201 | 8.375% | $1.397624 | 16.23% | 29,787.744 | 94.04% |
| standard | 2199 | 91.625% | $7.212114 | 83.77% | 1,887.561 | 5.96% |

Chi phí tăng thêm nếu so cùng request nhưng output thường = reasoning output/6: **$1.027946/ngày và 29,610.138 Wh/ngày**. Không gọi toàn bộ bill của nhóm reasoning là chi phí tăng thêm. Nếu chỉ tắt cờ reasoning và giữ nguyên token, USD tăng thêm = $0.000000; trong lab USD phụ thuộc token/tier, không có một phụ phí reasoning riêng.

| Trần reasoning | Request reroute | Reasoning còn lại | Tổng USD/ngày | Token mới | $/1M-token mới | Savings USD/ngày | Savings Wh/ngày |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10% | 0 | 201 | $8.609738 | 7,533,027 | $1.143 | $0.000000 | 0.000 |
| 5% | 81 | 120 | $7.642586 | 7,187,862 | $1.063 | $0.967152 | 14,261.195 |

10% cao hơn tỷ lệ hiện tại nên savings bằng 0. Kịch bản 5% chọn request có incremental USD lớn nhất để ước lượng cơ hội, rồi giữ input/tier/cache/batch và chia output cho 6; mẫu số token cũng được tính lại. Quy tắc triển khai đề xuất: chạy standard trước, chỉ reasoning nếu calibrated confidence <0,70 hoặc task phức tạp đã được phân loại, trong quota. Dataset không có confidence/quality labels, nên ngưỡng này cần được hiệu chuẩn và đánh giá chất lượng/latency trước. Các cap là kịch bản thay thế, chưa cộng vào tổng tiết kiệm M5.

## Sustainability / Your Turn #5 — Carbon-aware scheduling

Code: `finops/carbon_schedule.py`, CLI `missions/m6_carbon_scheduling.py`. Query 800 token không reasoning có 0,24 Wh và 0,0912 gCO2e ở us-east-1; đây là query minh họa, không phải median đo từ dataset. Năng lượng job = catalog watts/1.000 × num_gpus × hours/day × days × 1,055. PUE=1, dùng nameplate power; chưa tính CPU, cooling, storage hoặc mạng. Baseline và các vùng dùng cùng overhead spot để chỉ đo tác động chuyển vùng.

| Job interruptible | Loại | Ngày ghi trong CSV | kWh | us-east-1 gCO2e | europe-north1 gCO2e | Giảm gCO2e |
|---|---|---:|---:|---:|---:|---:|
| job-train-llm | train | 14 | 1654.240 | 628,611.20 | 49,627.20 | 578,984.00 |
| job-train-embed | train | 5 | 84.400 | 32,072.00 | 2,532.00 | 29,540.00 |
| job-finetune | train | 3 | 26.586 | 10,102.68 | 797.58 | 9,305.10 |
| job-dev-sandbox | dev | 22 | 55.704 | 21,167.52 | 1,671.12 | 19,496.40 |
| job-batch-eval | infer | 30 | 66.465 | 25,256.70 | 1,993.95 | 23,262.75 |

Tổng theo số ngày riêng của từng job: **1,887.395 kWh**, gồm 1,789.000 kWh hữu ích và 98.395 kWh overhead. Tổng này không phải tháng 30 ngày của M3.

| Vùng | USD/kWh | gCO2e/kWh | Tiền điện USD | Carbon kgCO2e | Giảm USD vs east | Giảm kgCO2e vs east | Điểm cân bằng↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| us-east-1 | 0.120 | 380 | $226.487 | 717.210 | $0.000 | 0.000 | 0.5378 |
| us-west-2 | 0.070 | 120 | $132.118 | 226.487 | $94.370 | 490.723 | 0.1314 |
| europe-north1 | 0.090 | 30 | $169.866 | 56.622 | $56.622 | 660.588 | 0.1400 |
| europe-central2 | 0.180 | 660 | $339.731 | 1245.681 | $-113.244 | -528.471 | 1.0000 |
| us-east-wa | 0.055 | 90 | $103.807 | 169.866 | $122.681 | 547.345 | 0.0476 |

Sạch nhất: **europe-north1**, giảm 660.588 kgCO2e (92.11%) và $56.622 tiền điện. Rẻ nhất: **us-east-wa**, giảm $122.681 và 547.345 kgCO2e. Cân bằng nhất theo trọng số 50/50: **us-east-wa**. Điểm = 0,5×min-max(price) + 0,5×min-max(carbon); điểm thấp tốt hơn. Trọng số là ưu tiên công ty, không phải quy đổi gram CO2 ra USD.

Ưu tiên ba job training: riêng nhóm này chuyển tới vùng sạch nhất giảm 617.829 kgCO2e và $52.957. Hai job sandbox/eval được tính riêng trong JSON, cần kiểm tra deadline. Nếu giả lập mọi job lặp 30 ngày như M3: 4,459.485 kWh, vùng sạch nhất giảm 1560.820 kgCO2e và $133.785; vùng rẻ nhất giảm $289.867.

Carbon và tiền điện cùng giảm khi giảm Wh; đổi vùng còn thay đổi intensity và tariff. Giá điện giảm chưa chứng minh thuê GPU ở vùng đó rẻ hơn. Tiền điện thường đã nằm trong giá thuê cloud, nên khoản này không được cộng thêm vào savings M5. Scheduling ở đây là lựa chọn vùng theo snapshot, chưa có lịch intensity theo giờ để tối ưu thời điểm. Training ít nhạy latency hơn online inference; kiểm tra vị trí dữ liệu, egress/checkpoint, GPU availability, data residency và deadline trước khi chuyển vùng.

## Hành động ưu tiên cho NimbusAI

Ưu tiên theo savings USD/tháng trong lab; chưa có chi phí triển khai để tính ROI hoàn vốn chính xác.

| Ưu tiên | Hành động | Tiềm năng USD/tháng | % tổng savings | Kiểm tra trước triển khai |
|---:|---|---:|---:|---|
| 1 | Spot + checkpoint cho batch/training; reserved cho nhu cầu ổn định | $10,040 | 80.30% | Đo rework, deadline; xác nhận utilization và thời hạn commit |
| 2 | Cascade có quality gate, cache theo break-even, batch eval | $1,208 | 9.66% | Đánh giá chất lượng, p95 latency; log cache writes/TTL |
| 3 | Profile hai GPU bị gắn cờ, benchmark GPU thay thế | $655 | 5.24% | VRAM, bandwidth, tok/s và SLA giữ được |
| 4 | TTL sandbox và tắt/scale-to-zero GPU idle | $600 | 4.80% | Không tắt job đang chạy; kiểm tra queue và thời gian khởi động |

Idle automation dễ làm nên có thể triển khai song song với purchasing dù savings nhỏ hơn. Duy trì showback theo team/project, cảnh báo $/1M-token, budget USD và Wh cho reasoning; chỉ bắt đầu chargeback sau khi xác nhận owner. Thử scheduling vùng cho training, giữ online inference gần người dùng. Theo dõi savings thực hiện mỗi tuần thay vì chỉ dựa trên forecast.

## Tái lập và đối soát

```powershell
python data/generate.py
python missions/run_all.py
python missions/m6_carbon_scheduling.py
python verify.py
pytest -q
python validation/check_extensions.py
```

M5/verify sinh lại `report.md`, `savings.png`, `focus_export.csv`, `writeup.md` và `mission_results.json`. Nội dung phân tích và bài viết được tạo từ code, nên không mất khi verify ghi lại output. Các check mở rộng nằm trong `validation/`; bộ `tests/` gốc giữ nguyên. JSON lưu số liệu chưa làm tròn, nhóm reasoning, các cap, cache sensitivity và mọi vùng của từng job.

_Figures are June-2026 as-of snapshots; re-baseline before acting._
