"""Vietnamese report and concise write-up, derived from mission evidence."""
from __future__ import annotations


def technical_analysis(e: dict, baseline: float, optimized: float, levers: dict) -> str:
    m1, m2, m3, m4 = (e[key] for key in ("m1", "m2", "m3", "m4"))
    cache, reasoning = m2["cache"], m2["reasoning"]
    carbon = e["carbon"]
    horizon = carbon["listed_horizon"]
    total = horizon["totals"]
    savings = baseline - optimized
    lines = [
        "## Phạm vi và phương pháp tính",
        "",
        "Dữ liệu tổng hợp seed 25, snapshot minh họa tháng 6/2026; không cần GPU, cloud hoặc API key. "
        "M1 dùng 264 mẫu giờ của 11 GPU; M2/M4 dùng 2.400 request trong một ngày; M3 có 8 workload. "
        "Nguồn: `data/generate.py`, bốn CSV trong `data/`, và các hàm `finops/`.",
        "",
        "M5 giữ quy ước lab: một tháng = 30 ngày; dùng chi phí M2 làm tròn cent/ngày, "
        "chi phí M3 làm tròn USD/tháng, rồi làm tròn từng lever sang USD. "
        "Bảng M2 bên dưới giữ sáu chữ số thập phân để đối soát; chênh lệch nhỏ là do làm tròn.",
        "",
        "`$/1M-token = tổng USD / ((input_tokens + output_tokens)/1.000.000)`. "
        "Input đã cache vẫn nằm trong sản lượng token phục vụ; ba lever M2 dùng cùng mẫu số. "
        "Không quy đổi tổng hóa đơn M5 sang $/token vì workloads training chưa có số token đầu ra.",
        "",
        "Tổng M5 là kịch bản cộng bốn lever của lab. Telemetry và workloads chưa có liên kết resource/job "
        "để xác minh right-sizing/idle có trùng với tài nguyên được giảm giá purchasing hay không. "
        "Cần đối soát ở cấp resource và tính lại giá sau mỗi thay đổi trước khi xem đây là tiết kiệm đã thực hiện. "
        "M3 giả lập recurring 30 ngày cho mọi job và tính reserved theo giờ sử dụng; "
        "hợp đồng reserved thực tế có thể tính cả giờ không dùng. Không cam kết ba năm chỉ từ dữ liệu này.",
        "",
        "## M1 — Hiệu quả GPU và GPU-Util lie",
        "",
        "| GPU | Loại | GPU-Util (%) | MFU | MBU | Giờ idle/ngày |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for gpu in m1["summary"]:
        lines.append(f"| {gpu['gpu_id']} | {gpu['gpu_type']} | {gpu['gpu_util_pct']:.1f} | "
                     f"{gpu['mfu']:.3f} | {gpu['mbu']:.3f} | {gpu['idle_hours']} |")
    highest = max(m1["summary"], key=lambda gpu: gpu["gpu_util_pct"])
    lines += [
        "",
        f"GPU-Util cao nhất: **{highest['gpu_id']}**, {highest['gpu_util_pct']:.1f}%, "
        f"nhưng MFU chỉ {highest['mfu']:.3f}. Các GPU bị gắn cờ: "
        + ", ".join(f"`{gpu['gpu_id']}`" for gpu in m1["lies"]) + ".",
        "",
        "GPU-Util đo tỷ lệ thời gian GPU có kernel hoạt động trong cửa sổ lấy mẫu; "
        "MFU đo achieved TFLOPs/peak TFLOPs. Kernel có thể hoạt động nhưng chờ bộ nhớ, "
        "phụ thuộc dữ liệu hoặc dùng ít tensor core; kernel nhỏ và overhead điều phối cũng làm throughput thấp. "
        "Vì vậy GPU-Util cao chưa chứng minh GPU tạo nhiều FLOPs hữu ích. Đây là các nguyên nhân cần profile, "
        "chưa phải chẩn đoán nguyên nhân từ telemetry. Với decode, xem thêm MBU; "
        "MBU thấp một mình chưa đủ kết luận memory-bound. Roofline so arithmetic intensity với ridge point: "
        "decode 1–2 FLOP/byte thấp hơn ~295 trên H100, còn prefill ~455 cao hơn ngưỡng này.",
        "",
        "| GPU gắn cờ | Đề xuất trong M5 | Giảm $/GPU-giờ | Tiềm năng USD/30 ngày |",
        "|---|---|---:|---:|",
    ]
    for row in e["rightsize"]:
        lines.append(f"| {row['gpu_id']} | {row['current']} → {row['target']} | "
                     f"${row['hourly_delta']:.2f} | ${row['monthly_savings']:.2f} |")
    lines += [
        "",
        "Hạ GPU trong M5 là giả thuyết tiết kiệm: phải kiểm tra VRAM, bandwidth, tok/s và latency trước. "
        "Đặc biệt H100→A100 giảm peak TFLOPs, A10G→L4 giảm peak bandwidth; "
        "không thể khẳng định cùng hiệu năng chỉ từ MFU thấp.",
        "",
        f"Idle tại `gpu-h100-5`: 8 giờ × $2,50 = **${m1['idle_waste_daily']:.2f}/ngày**, "
        f"hay **${m1['idle_waste_daily']*30:,.0f}/tháng**, chiếm "
        f"{m1['idle_waste_daily']*30/baseline*100:.2f}% baseline M5. "
        "Dùng TTL cho sandbox, lịch tắt qua đêm và kiểm tra job/queue trước khi scale-to-zero.",
        "",
        "## M2 — Baseline/optimized theo $/1M-token",
        "",
        f"{m2['request_count']:,} request; **{m2['total_tokens']:,} input + output tokens/ngày**. "
        f"Baseline ${m2['baseline_daily']:.2f}/ngày → ${m2['optimized_daily']:.2f}/ngày; "
        f"**${m2['baseline_per_m']:.3f} → ${m2['optimized_per_m']:.3f}/1M-token**, "
        f"tiết kiệm **{m2['savings_pct']:.1f}%**.",
        "",
        "| Bước áp dụng tuần tự | USD/ngày | $/1M-token | Savings thêm USD/ngày |",
        "|---|---:|---:|---:|",
    ]
    for stage in m2["stages"]:
        lines.append(f"| {stage['name']} | ${stage['daily_usd']:.6f} | ${stage['per_m']:.3f} | "
                     f"${stage['incremental_savings_daily']:.6f} |")
    cascade = m2["stages"][1]["incremental_savings_daily"]
    lines += [
        "",
        f"Cascade đóng góp lớn nhất trong inference: ${cascade:.6f}/ngày "
        f"(~{cascade/(m2['baseline_daily_exact']-m2['optimized_daily_exact'])*100:.1f}% tổng savings M2). "
        "Đây là attribution theo thứ tự cascade→cache→batch; đổi thứ tự sẽ đổi phần đóng góp do tương tác chiết khấu. "
        "Small có giá input/output $0,20/$0,40 mỗi triệu token so với large $3/$15. "
        "Chỉ route request phù hợp chất lượng sang small. Batch dành cho eval hoặc tác vụ không cần trả lời real-time; "
        "không áp dụng mặc định cho chat cần latency thấp.",
        "",
        "`discount_stack(batch=True, cache_hit_frac=1)=0,5×0,1=0,05`: "
        "95% off chỉ cho phần input lý tưởng đã cache 100%, chưa tính output, phí ghi và lưu trữ. "
        "Không dùng 95% này thay cho mức tiết kiệm thực tế toàn bộ request.",
        "",
        "## M3 — Purchasing theo workload",
        "",
        f"On-demand **${m3['on_demand_monthly']:,.0f}/tháng** → "
        f"spot/reserved **${m3['optimized_monthly']:,.0f}/tháng**, "
        f"tiết kiệm **{m3['savings_pct']:.1f}%**. Ngưỡng minh họa reserved discount 45%: "
        "duty cycle ≥55% (=13,2 giờ/ngày). Giá catalog từng GPU có discount khác nhau; "
        "policy M3 dùng ngưỡng chung, nên cần tính lại ngưỡng và điều khoản cụ thể trước khi commit.",
        "",
        "| Job | GPU | Tier | On-demand USD/tháng | Optimized USD/tháng |",
        "|---|---|---|---:|---:|",
    ]
    for row in m3["recommendations"]:
        lines.append(f"| {row['job_id']} | {row['gpu_type']} | {row['tier']} | "
                     f"${row['on_demand']:,.0f} | ${row['optimized']:,.0f} |")
    lines += [
        "",
        "Các job interruptible dưới 24 giờ/ngày dùng spot; ba workload inference ổn định dùng reserved. "
        "Checkpoint simulation tính effective GPU-hours = useful GPU-hours × "
        "(1+0,03+0,05×0,5)=1,055×: 3% checkpoint cộng rework kỳ vọng 2,5%. "
        "Giờ thực trả cao hơn giờ hữu ích, nhưng giá spot vẫn giúp tổng tiền giảm. "
        "Giữ on-demand cho burst/nhu cầu chưa dự báo được; reserved chỉ cho nhu cầu ổn định đủ dài.",
        "",
        "## M4 — Showback, chargeback và FOCUS",
        "",
        "| Team | USD/ngày | Tỷ trọng chi phí |",
        "|---|---:|---:|",
    ]
    for team, amount in sorted(m4["by_team_exact"].items(), key=lambda item: -item[1]):
        lines.append(f"| {team} | ${amount:.6f} | {amount/m4['total_daily']*100:.2f}% |")
    lead, amount = max(m4["by_team_exact"].items(), key=lambda item: item[1])
    lines += [
        "",
        f"Team **{lead}** chi nhiều nhất ({amount/m4['total_daily']*100:.2f}%). "
        f"Tag `team` + `project` đầy đủ: {m4['tagged_count']}/{m4['request_count']} "
        f"= {m4['tag_coverage']*100:.1f}% (làm tròn ~92%); vượt gate 80%, "
        f"chargeback ready = **{m4['chargeback_ready']}** theo tiêu chí lab. "
        "Coverage cao giúp tránh phân bổ phần lớn hóa đơn bằng phỏng đoán; vẫn cần xác nhận owner "
        "cho project chưa gắn tag, thống nhất ngân sách và xử lý chi phí dùng chung.",
        "",
        f"`focus_export.csv` xuất **{m4['focus_rows']:,} request**, mỗi request có ResourceId riêng; "
        f"tổng BilledCost ≈ **${m4['total_daily']:.6f}/ngày**, cùng chính sách cache-write như M2. "
        "Giữ 12 chữ số thập phân khi xuất để đối soát request nhỏ. Đây là schema FOCUS-style tối giản của lab, "
        "giúp chuẩn hóa tiền tệ, kỳ tính phí và tags giữa nhà cung cấp; chưa phải bộ dữ liệu chứng nhận đầy đủ FOCUS.",
        "",
        "## Your Turn #3 — Kinh tế cache",
        "",
        "Code: `pricing.cache_is_worth_it()` và `cache_economics.analyze_cache()`; "
        "được áp dụng trước khi tính cache savings trong M2/M4. "
        "Đặt `write_cost=1,25` là tổng giá ghi so với input thường, `read_discount=0,10` là phần giá còn lại khi đọc. "
        "Với một lần ghi và n lần đọc lại: không cache trả (1+n)P, cache trả (1,25+0,10n)P. "
        "Chỉ cache khi `n > (1,25−1)/(1−0,10)=0,277778`; bằng ngưỡng chưa tạo savings. "
        "Một lần đọc lại nguyên prefix đã vượt ngưỡng; n trung bình có thể là số thập phân.",
        "",
        "Dataset không có `avg_cache_reads`, prompt ID, cache-write event hoặc TTL. "
        "Ước lượng write-equivalent tokens = cacheable input − cached input, "
        "với cacheable fraction từ generator: assistant/rag 70%, team khác 10%. "
        "Reuse = cached read tokens/write-equivalent tokens; gate dùng tỷ lệ có trọng số batch. "
        "Đây là tỷ lệ tái dùng quy đổi theo token, không phải số lần đọc prefix đã quan sát. "
        "Hàm cũng hỗ trợ `avg_cache_reads` do caller cung cấp; dữ liệu thực cần log prefix/TTL để kiểm định.",
        "",
        "| Tier | Giá input/ghi/đọc USD/1M | Ngưỡng n | Reuse ước lượng | Reuse trọng số batch | Gate | Net savings USD/ngày* |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for tier, row in cache["tiers"].items():
        lines.append(f"| {tier} | {row['input_price_per_m']:.2f}/{row['write_price_per_m']:.2f}/{row['read_price_per_m']:.2f} | "
                     f"{row['break_even_reads']:.6f} | {row['avg_reads']:.6f} | {row['effective_avg_reads']:.6f} | "
                     f"{'Bật' if row['cache_enabled'] else 'Tắt'} | ${row['savings_daily']:.6f} |")
    lines += [
        "",
        f"*Giữ cascade và batch cố định: không cache ${cache['no_cache_daily']:.6f} → "
        f"cache có phí ghi ${cache['gated_daily']:.6f}/ngày, net saving "
        f"${cache['savings_daily']:.6f} ({cache['savings_pct']:.2f}%). "
        "Khác attribution M2 vì ở đây batch đã bật trước khi so cache.",
        "",
        f"Phí ghi thêm **${cache['write_premium_daily']:.6f}/ngày**. "
        f"Kết quả gốc coi ghi miễn phí: ${m2['legacy_optimized_daily']:.6f}/ngày; "
        f"kết quả mới: ${m2['optimized_daily_exact']:.6f}/ngày. "
        "Hai tier cùng ngưỡng vì dùng cùng hệ số giá; large tiết kiệm USD nhiều hơn vì giá input cao hơn. "
        "Hệ số ghi 1,25 là giả định bổ sung của bài, chưa tính phí storage/TTL.",
        "",
        "| Sensitivity n | Gate | Savings theo đơn vị giá input P |",
        "|---:|---|---:|",
    ]
    for row in cache["sensitivity"]:
        lines.append(f"| {row['avg_reads']:.6f} ({row['case']}) | {'Bật' if row['cache_enabled'] else 'Tắt'} | "
                     f"{row['saving_input_price_units']:.6f} |")
    lines += [
        "",
        "## Your Turn #4 — Ngân sách reasoning",
        "",
        "Code: `finops/reasoning.py`, được M2/M5 gọi. Giá USD dùng chính policy M2; "
        "năng lượng dùng `wh_per_query` = 0,30 Wh/1.000 token, nhân 80 khi reasoning. "
        "Đây là mô hình năng lượng, không phải watt đo từ GPU. Generator đã tăng output reasoning 6×; "
        "hệ số 80 áp lên số token đó nên không thể nói mọi reasoning request chỉ tốn đúng 80× "
        "so với câu trả lời thường có số token khác. Giữ nguyên cùng số token thì tỷ số Wh mới đúng 80×.",
        "",
        "| Traffic | Request | % traffic | USD/ngày | % chi phí | Wh/ngày | % năng lượng |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in reasoning["groups"].items():
        lines.append(f"| {name} | {row['requests']} | {row['traffic_pct']:.3f}% | ${row['cost_usd']:.6f} | "
                     f"{row['cost_share_pct']:.2f}% | {row['wh']:,.3f} | {row['energy_share_pct']:.2f}% |")
    inc = reasoning["incremental_reasoning"]
    lines += [
        "",
        f"Chi phí tăng thêm nếu so cùng request nhưng output thường = reasoning output/6: "
        f"**${inc['cost_usd']:.6f}/ngày và {inc['wh']:,.3f} Wh/ngày**. "
        "Không gọi toàn bộ bill của nhóm reasoning là chi phí tăng thêm. "
        f"Nếu chỉ tắt cờ reasoning và giữ nguyên token, USD tăng thêm = ${inc['same_token_extra_cost_usd']:.6f}; "
        "trong lab USD phụ thuộc token/tier, không có một phụ phí reasoning riêng.",
        "",
        "| Trần reasoning | Request reroute | Reasoning còn lại | Tổng USD/ngày | Token mới | $/1M-token mới | Savings USD/ngày | Savings Wh/ngày |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario in reasoning["scenarios"].values():
        t = scenario["totals"]
        lines.append(f"| {scenario['cap_pct']:.0f}% | {scenario['rerouted_requests']} | {scenario['after_reasoning_requests']} | "
                     f"${t['cost_usd']:.6f} | {t['total_tokens']:,} | ${t['cost_per_million_tokens_usd']:.3f} | "
                     f"${scenario['cost_savings_usd']:.6f} | {scenario['energy_savings_wh']:,.3f} |")
    lines += [
        "",
        "10% cao hơn tỷ lệ hiện tại nên savings bằng 0. Kịch bản 5% chọn request có incremental USD lớn nhất "
        "để ước lượng cơ hội, rồi giữ input/tier/cache/batch và chia output cho 6; mẫu số token cũng được tính lại. "
        "Quy tắc triển khai đề xuất: chạy standard trước, chỉ reasoning nếu calibrated confidence <0,70 "
        "hoặc task phức tạp đã được phân loại, trong quota. Dataset không có confidence/quality labels, "
        "nên ngưỡng này cần được hiệu chuẩn và đánh giá chất lượng/latency trước. "
        "Các cap là kịch bản thay thế, chưa cộng vào tổng tiết kiệm M5.",
        "",
        "## Sustainability / Your Turn #5 — Carbon-aware scheduling",
        "",
        "Code: `finops/carbon_schedule.py`, CLI `missions/m6_carbon_scheduling.py`. "
        "Query 800 token không reasoning có 0,24 Wh và 0,0912 gCO2e ở us-east-1; "
        "đây là query minh họa, không phải median đo từ dataset. "
        "Năng lượng job = catalog watts/1.000 × num_gpus × hours/day × days × 1,055. "
        "PUE=1, dùng nameplate power; chưa tính CPU, cooling, storage hoặc mạng. "
        "Baseline và các vùng dùng cùng overhead spot để chỉ đo tác động chuyển vùng.",
        "",
        "| Job interruptible | Loại | Ngày ghi trong CSV | kWh | us-east-1 gCO2e | europe-north1 gCO2e | Giảm gCO2e |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for job in horizon["jobs"]:
        regions = {r["region"]: r for r in job["regions"]}
        old, clean = regions[carbon["baseline_region"]], regions[carbon["objectives"]["cleanest"]]
        lines.append(f"| {job['job_id']} | {job['kind']} | {job['days']:g} | {job['energy_kwh']:.3f} | "
                     f"{old['carbon_g']:,.2f} | {clean['carbon_g']:,.2f} | {clean['carbon_savings_g']:,.2f} |")
    lines += [
        "",
        f"Tổng theo số ngày riêng của từng job: **{total['energy_kwh']:,.3f} kWh**, "
        f"gồm {total['useful_energy_kwh']:,.3f} kWh hữu ích và {total['spot_overhead_energy_kwh']:.3f} kWh overhead. "
        "Tổng này không phải tháng 30 ngày của M3.",
        "",
        "| Vùng | USD/kWh | gCO2e/kWh | Tiền điện USD | Carbon kgCO2e | Giảm USD vs east | Giảm kgCO2e vs east | Điểm cân bằng↓ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in horizon["regions"]:
        lines.append(f"| {row['region']} | {row['price_usd_per_kwh']:.3f} | {row['carbon_g_per_kwh']:.0f} | "
                     f"${row['electricity_usd']:.3f} | {row['carbon_g']/1000:.3f} | "
                     f"${row['electricity_savings_usd']:.3f} | {row['carbon_savings_g']/1000:.3f} | {row['balanced_score']:.4f} |")
    clean, cheap = total["cleanest"], total["cheapest"]
    training = horizon["subsets"]["training"]["totals"]["cleanest"]
    monthly = carbon["normalized_30_days"]["totals"]
    lines += [
        "",
        f"Sạch nhất: **{clean['region']}**, giảm {clean['carbon_savings_g']/1000:.3f} kgCO2e "
        f"({clean['carbon_savings_g']/total['baseline_carbon_g']*100:.2f}%) và ${clean['electricity_savings_usd']:.3f} tiền điện. "
        f"Rẻ nhất: **{cheap['region']}**, giảm ${cheap['electricity_savings_usd']:.3f} và "
        f"{cheap['carbon_savings_g']/1000:.3f} kgCO2e. "
        f"Cân bằng nhất theo trọng số 50/50: **{carbon['objectives']['balanced']}**. "
        "Điểm = 0,5×min-max(price) + 0,5×min-max(carbon); điểm thấp tốt hơn. "
        "Trọng số là ưu tiên công ty, không phải quy đổi gram CO2 ra USD.",
        "",
        f"Ưu tiên ba job training: riêng nhóm này chuyển tới vùng sạch nhất giảm "
        f"{training['carbon_savings_g']/1000:.3f} kgCO2e và ${training['electricity_savings_usd']:.3f}. "
        "Hai job sandbox/eval được tính riêng trong JSON, cần kiểm tra deadline. "
        f"Nếu giả lập mọi job lặp 30 ngày như M3: {monthly['energy_kwh']:,.3f} kWh, "
        f"vùng sạch nhất giảm {monthly['cleanest']['carbon_savings_g']/1000:.3f} kgCO2e "
        f"và ${monthly['cleanest']['electricity_savings_usd']:.3f}; "
        f"vùng rẻ nhất giảm ${monthly['cheapest']['electricity_savings_usd']:.3f}.",
        "",
        "Carbon và tiền điện cùng giảm khi giảm Wh; đổi vùng còn thay đổi intensity và tariff. "
        "Giá điện giảm chưa chứng minh thuê GPU ở vùng đó rẻ hơn. Tiền điện thường đã nằm trong giá thuê cloud, "
        "nên khoản này không được cộng thêm vào savings M5. Scheduling ở đây là lựa chọn vùng theo snapshot, "
        "chưa có lịch intensity theo giờ để tối ưu thời điểm. Training ít nhạy latency hơn online inference; "
        "kiểm tra vị trí dữ liệu, egress/checkpoint, GPU availability, data residency và deadline trước khi chuyển vùng.",
        "",
        "## Hành động ưu tiên cho NimbusAI",
        "",
        "Ưu tiên theo savings USD/tháng trong lab; chưa có chi phí triển khai để tính ROI hoàn vốn chính xác.",
        "",
        "| Ưu tiên | Hành động | Tiềm năng USD/tháng | % tổng savings | Kiểm tra trước triển khai |",
        "|---:|---|---:|---:|---|",
    ]
    actions = {
        "Purchasing (spot/reserved)": ("Spot + checkpoint cho batch/training; reserved cho nhu cầu ổn định", "Đo rework, deadline; xác nhận utilization và thời hạn commit"),
        "Inference (cascade/cache/batch)": ("Cascade có quality gate, cache theo break-even, batch eval", "Đánh giá chất lượng, p95 latency; log cache writes/TTL"),
        "Right-size util-lies": ("Profile hai GPU bị gắn cờ, benchmark GPU thay thế", "VRAM, bandwidth, tok/s và SLA giữ được"),
        "Kill idle GPUs": ("TTL sandbox và tắt/scale-to-zero GPU idle", "Không tắt job đang chạy; kiểm tra queue và thời gian khởi động"),
    }
    for rank, (name, amount) in enumerate(sorted(levers.items(), key=lambda item: -item[1]), 1):
        action, check = actions[name]
        lines.append(f"| {rank} | {action} | ${amount:,.0f} | {amount/savings*100:.2f}% | {check} |")
    lines += [
        "",
        "Idle automation dễ làm nên có thể triển khai song song với purchasing dù savings nhỏ hơn. "
        "Duy trì showback theo team/project, cảnh báo $/1M-token, budget USD và Wh cho reasoning; "
        "chỉ bắt đầu chargeback sau khi xác nhận owner. Thử scheduling vùng cho training, "
        "giữ online inference gần người dùng. Theo dõi savings thực hiện mỗi tuần thay vì chỉ dựa trên forecast.",
        "",
        "## Tái lập và đối soát",
        "",
        "```powershell",
        "python data/generate.py",
        "python missions/run_all.py",
        "python missions/m6_carbon_scheduling.py",
        "python verify.py",
        "pytest -q",
        "python validation/check_extensions.py",
        "```",
        "",
        "M5/verify sinh lại `report.md`, `savings.png`, `focus_export.csv`, `writeup.md` và "
        "`mission_results.json`. Nội dung phân tích và bài viết được tạo từ code, nên không mất khi verify ghi lại output. "
        "Các check mở rộng nằm trong `validation/`; bộ `tests/` gốc giữ nguyên. "
        "JSON lưu số liệu chưa làm tròn, nhóm reasoning, các cap, cache sensitivity và mọi vùng của từng job.",
    ]
    return "\n".join(lines)


def build_writeup(e: dict, baseline: float, optimized: float, levers: dict) -> str:
    """Answer the five required prompts in a short submission companion."""
    m1, m2, m3, m4 = (e[key] for key in ("m1", "m2", "m3", "m4"))
    cache, reasoning = m2["cache"], m2["reasoning"]
    group = reasoning["groups"]["reasoning"]
    cap5 = reasoning["scenarios"]["cap_5_pct"]
    carbon = e["carbon"]["listed_horizon"]["totals"]
    clean, cheap = carbon["cleanest"], carbon["cheapest"]
    savings = baseline - optimized
    lines = [
        "# Bài viết ngắn — GPU FinOps tại NimbusAI",
        "",
        "## 1. Chi phí trước và sau tối ưu",
        "",
        f"Tôi dùng dữ liệu tổng hợp seed 25 để đo chi phí trên sản lượng input + output token. "
        f"Inference phục vụ {m2['request_count']:,} request và {m2['total_tokens']:,} token/ngày. "
        f"Baseline chạy tất cả trên large, không cache/batch, tốn ${m2['baseline_daily']:.2f}/ngày "
        f"hay ${m2['baseline_per_m']:.3f}/1M-token. Sau cascade, cache có phí ghi và batch, "
        f"chi phí còn ${m2['optimized_daily']:.2f}/ngày, ${m2['optimized_per_m']:.3f}/1M-token, "
        f"giảm {m2['savings_pct']:.1f}%. Đơn vị $/token phản ánh throughput hữu ích, "
        "trong khi $/GPU-giờ chỉ phản ánh giá thuê.",
        "",
        f"Kịch bản tổng M5 giảm từ ${baseline:,.0f} xuống ${optimized:,.0f}/30 ngày, "
        f"tiết kiệm ${savings:,.0f}, tương đương {savings/baseline*100:.1f}%. "
        "Đây là forecast minh họa theo quy ước lab. Training không có token đầu ra để quy đổi "
        "tổng M5 thành $/1M-token; cần đối soát resource để tránh trùng savings purchasing/right-sizing/idle.",
        "",
        "## 2. Đòn bẩy hiệu quả nhất",
        "",
        f"Purchasing đóng góp lớn nhất: ${levers['Purchasing (spot/reserved)']:,.0f}/tháng, "
        f"{levers['Purchasing (spot/reserved)']/savings*100:.1f}% tổng savings. "
        f"M3 giảm ${m3['on_demand_monthly']:,.0f} xuống ${m3['optimized_monthly']:,.0f} "
        f"({m3['savings_pct']:.1f}%) nhờ spot cho job interruptible và reserved cho inference ổn định. "
        "Spot đã tính 5,5% overhead checkpoint/rework. Reserved cần nhu cầu ổn định đủ lâu; "
        "không thể suy ra cam kết ba năm an toàn từ một ngày telemetry.",
        "",
        f"Inference tiết kiệm ${levers['Inference (cascade/cache/batch)']:,.0f}/tháng; "
        f"right-sizing tiềm năng ${levers['Right-size util-lies']:,.0f}; "
        f"tắt idle ${levers['Kill idle GPUs']:,.0f}. Trong inference, cascade có tác động lớn nhất "
        f"(${m2['stages'][1]['incremental_savings_daily']:.3f}/ngày), vì đa số request "
        "được route sang small. Phân rã cache/batch phụ thuộc thứ tự áp dụng, "
        "nên tôi dùng cùng thứ tự cascade→cache→batch để tránh cộng lặp chiết khấu.",
        "",
        "## 3. GPU-Util lie và tác động tài chính",
        "",
        "GPU-Util là tỷ lệ thời gian kernel hoạt động, không phải tỷ lệ FLOPs hữu ích. "
        "Kernel chờ bộ nhớ hoặc chỉ dùng ít tensor core vẫn có thể làm GPU-Util cao. "
        "MFU = achieved/peak FLOPs và MBU = achieved/peak bandwidth giúp thấy hiệu quả thực. "
        + "; ".join(f"{gpu['gpu_id']}: Util {gpu['gpu_util_pct']:.1f}%, MFU {gpu['mfu']:.3f}" for gpu in m1["lies"])
        + ". Hai GPU này cần profiling trước khi hạ cấu hình; MFU thấp chưa chứng minh nguyên nhân cụ thể "
        "hoặc khả năng giữ nguyên hiệu năng trên GPU rẻ hơn.",
        "",
        f"M5 mô phỏng H100→A100 và A10G→L4, tiết kiệm ${levers['Right-size util-lies']:,.0f}/tháng. "
        f"Ngoài ra gpu-h100-5 idle 8 giờ/ngày làm mất ${m1['idle_waste_daily']:.0f}/ngày. "
        "Tôi kiểm tra VRAM, bandwidth, tok/s và p95 latency trước right-sizing, "
        "đồng thời dùng TTL/lịch tắt để chấm dứt tiền thuê khi GPU không tạo giá trị.",
        "",
        "## 4. Ba phần mở rộng đã thực hiện",
        "",
        f"**Cache (#3):** thêm `cache_is_worth_it()` và phí ghi 1,25×, đọc 0,10× giá input. "
        f"Ngưỡng đọc lại là n>{cache['break_even_reads']:.6f}. "
        f"Reuse quy đổi theo token ước lượng của small/large là "
        f"{cache['tiers']['small']['avg_reads']:.3f}/{cache['tiers']['large']['avg_reads']:.3f}, nên cả hai bật cache. "
        f"Giữ cascade/batch cố định, bill ${cache['no_cache_daily']:.6f} → ${cache['gated_daily']:.6f}/ngày "
        f"(giảm {cache['savings_pct']:.2f}%). Dataset không có prompt ID/avg_cache_reads; "
        "ước lượng dựa trên cacheable fraction của generator, cần log thực để xác nhận.",
        "",
        f"**Reasoning (#4):** {group['requests']} request ({group['traffic_pct']:.3f}% traffic) "
        f"chiếm {group['cost_share_pct']:.2f}% USD nhưng {group['energy_share_pct']:.2f}% Wh. "
        "80× Wh là giả định mô hình áp sau output 6× của generator, không phải phép đo GPU. "
        "Trần 10% không thay đổi gì vì traffic hiện thấp hơn trần. "
        f"Trần 5% mô phỏng reroute {cap5['rerouted_requests']} request, tiết kiệm "
        f"${cap5['cost_savings_usd']:.6f}/ngày và {cap5['energy_savings_wh']/1000:.3f} kWh/ngày "
        f"({cap5['energy_savings_pct']:.2f}% năng lượng). Rule đề xuất: standard trước, "
        "reasoning khi confidence đã hiệu chuẩn <0,70 hoặc task phức tạp đã được xác nhận; "
        "cần đánh giá chất lượng vì output và mẫu số token đều giảm.",
        "",
        f"**Carbon (#5):** tính đủ năm job interruptible, so sánh năm vùng theo điện và carbon. "
        f"Theo số ngày trong CSV, tổng {carbon['energy_kwh']:,.3f} kWh gồm overhead spot. "
        f"Chuyển sang europe-north1 giảm {clean['carbon_savings_g']/1000:.3f} kgCO2e "
        f"và ${clean['electricity_savings_usd']:.3f} tiền điện. us-east-wa rẻ nhất và thắng "
        f"điểm cân bằng 50/50, giảm ${cheap['electricity_savings_usd']:.3f} và "
        f"{cheap['carbon_savings_g']/1000:.3f} kgCO2e. "
        "Training là ứng viên chuyển vùng trước; kiểm tra egress, deadline và vị trí dữ liệu. "
        "Tiền điện thường nằm trong thuê cloud, nên không cộng khoản này hoặc kịch bản reasoning vào M5.",
        "",
        "## 5. Ba khuyến nghị đầu tiên",
        "",
        "1. **Tối ưu purchasing:** chuyển job phù hợp sang spot có checkpoint; chỉ reserved "
        "cho nhu cầu được dự báo ổn định, sau khi đối soát giá, utilization và kỳ cam kết.",
        "2. **Tối ưu inference có quality gate:** cascade trước, cache khi vượt break-even và log writes/TTL, "
        "batch eval; quản lý reasoning bằng cả ngân sách USD và Wh, kiểm tra SLA trước khi áp quota.",
        f"3. **Thiết lập trách nhiệm vận hành:** showback theo team/project, bổ sung tags "
        f"(coverage hiện {m4['tag_coverage']*100:.1f}%), tự động tắt idle, benchmark right-sizing; "
        "thử chuyển training tới vùng phù hợp mục tiêu tiền điện/carbon và theo dõi savings thực hiện hàng tuần.",
        "",
        "_Bài viết được M5 tạo từ cùng số liệu với report.md; xem report và mission_results.json để đối soát._",
    ]
    return "\n".join(lines) + "\n"
