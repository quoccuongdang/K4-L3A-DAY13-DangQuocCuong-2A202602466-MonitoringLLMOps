 Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Đặng Quốc Cường
- **MSSV:** 2A202602466
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/quoccuongdang/K4-L3A-DAY13-DangQuocCuong-2A202602466-MonitoringLLMOps
- **Commit SHA cuối:** `d3c5744472a820c08539e973a70f0fd557c55566`
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602466`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đã bổ sung correlation ID, context enrichment và PII scrubbing đạt chuẩn |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ toàn bộ 6 panel trong contract |
| `pytest` | 22 passed | 24 passed | 100% test passed (bổ sung tests CCCD và credit card) |
| Số traces hợp lệ | 0 (chưa có child span) | > 20 traces | Đầy đủ quan hệ cha-con (agent -> retrieval & generation) |
| Số PII leak | 0 | 0 | Không phát hiện rò rỉ PII trong log |
| Latency P95 / TTFT P95 | ~2071.8ms / 50ms | 1077.8ms / 50ms | Phản hồi ổn định, nằm trong ngưỡng SLO 3000ms |
| Retrieval success rate | N/A | 100% | Hoạt động bình thường ở chế độ baseline |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` xóa context cũ bằng `clear_contextvars()`, nhận header `x-request-id` hoặc sinh mới dạng `req-<8-hex>` (`req-{uuid.uuid4().hex[:8]}`). Sau đó bind vào contextvars qua `bind_contextvars(correlation_id=correlation_id)` và trả về cho client qua 2 header `x-request-id` và `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `user_id_hash` (sha256 12 ký tự), `session_id`, `feature`, `model`, `env`, `correlation_id`, `service="api"`. Ở log `response_sent` bổ sung: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Đăng ký processor `scrub_event` vào structlog ngay trước `JsonlFileProcessor` và `JSONRenderer`. Bộ xử lý quét đệ quy các trường trong `payload` và các trường văn bản, che các định dạng email, số điện thoại Việt Nam, CCCD 12 số, thẻ thanh toán thành các token `[REDACTED_...]`.
- **Cách kiểm chứng kết quả:** Chạy `python scripts/validate_logs.py` đạt 100/100, chạy test `pytest tests/test_pii.py` (24/24 passed), và kiểm tra thủ công file `data/logs.jsonl`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Traces được gửi vào project `day13-k4-l3a-2A202602466` trên tài khoản Langfuse cá nhân (Đặng's Organization), có tags `lab`, `qa`, model `claude-sonnet-4-5` và user_id hash tương ứng.
- **Cấu trúc root/retrieval/generation observations:** Root trace `day13-agent-request` chứa Agent observation `lab-agent-run`, bên dưới gồm 2 child observations: `retrieval` (loại span) và `fake-llm-generate` (loại generation ghi nhận tokens, cost, ttft).
- **Cách nối trace với log:** Gắn `correlation_id` vào `metadata` của trace và observation cha, khớp 1-1 với trường `correlation_id` trong file `data/logs.jsonl`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (`baseline`, `production`)
- **Version/label candidate:** Version 2 (`candidate`)
- **Trace ID của mỗi version:**
  - Version 1 (production / rollback): trace `req-b96f4260` (Trace ID: `95e721a8fff58307bdf79d222b281010`)
  - Version 2 (candidate): trace `req-b2b8ce7e`
- **Cách promote và rollback `production`:** Sử dụng API `update_prompt` của Langfuse SDK (hoặc giao diện web Langfuse) để chuyển nhãn `production` sang Version 2 khi release, sau đó đổi nhãn `production` về lại Version 1 để thực hiện rollback an toàn.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng giao diện runtime trực tiếp tại `/dashboard` từ `data/logs.jsonl` gồm 6 panel: Latency percentiles & TTFT, Request Traffic, Errors & Retrieval, Cost Over Time, Input & Output Tokens, Quality Proxy (cửa sổ 60m, refresh 30s).
- **SLO và lý do chọn:** `primary_slo.fast_successful_requests` với mục tiêu 99.5% request thành công có latency &le; 3000ms trong 28 ngày. Ngưỡng 3000ms được chọn vì baseline thực tế ~1077ms, đủ rộng để chịu biến động tải nhẹ nhưng sẽ kích hoạt ngay khi RAG bị nghẽn (> 2500ms).
- **Cách tính error budget:** Error budget = `100% - 99.5% = 0.5%` tổng số request trong 28 ngày. Hệ thống chỉ cho phép tối đa 0.5% request bị chậm hoặc lỗi.
- **Ba alert và runbook tương ứng:**
  1. `high_tail_latency` (warning): P95 latency > 3000ms trong 5m -> Runbook: [docs/alerts.md#alert-1](../docs/alerts.md#alert-1).
  2. `high_error_rate` (critical): error rate > 2% trong 3m -> Runbook: [docs/alerts.md#alert-2](../docs/alerts.md#alert-2).
  3. `retrieval_degradation` (critical): retrieval success < 90% trong 5m -> Runbook: [docs/alerts.md#alert-3](../docs/alerts.md#alert-3).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 17:24 – 17:26 (UTC: 10:24:44 – 10:25:00)
- **Triệu chứng từ metrics:** Panel 1 (Latency & TTFT) cho thấy hiện tượng tail latency tăng đột biến: Latency P99 vọt lên **4256.1 ms** và Latency P95 đạt **2848.5 ms** (vượt ngưỡng cho phép của challenge 2000 ms), trong khi TTFT P95 vẫn duy trì mức thấp 50 ms.
- **Log line và correlation ID liên quan:** Lọc log trong khoảng thời gian xảy ra sự cố phát hiện request có độ trễ lớn nhất là **`req-a0b69bf4`** với `latency_ms = 4608` (session: `k4-l3a-challenge-s01`, user_id_hash: `dde2e75b20cf`, feature: `monitoring`). Log `response_sent` ghi nhận:
  ```json
  {"service": "api", "latency_ms": 4608, "ttft_ms": 50, "tool_name": "retrieval", "tool_success": true, "event": "response_sent", "correlation_id": "req-a0b69bf4", "session_id": "k4-l3a-challenge-s01"}
  ```
- **Trace ID và span gây ảnh hưởng:** Trace ID tương ứng trên Langfuse là **`09b5321e95b9c1493ea47d343ce11642`**. Quan sát span waterfall cho thấy:
  - `lab-agent-run` (Agent): tổng thời gian 4.609s
  - `retrieval` (Span): thời gian chiếm **2.502s** (chiếm phần lớn độ trễ)
  - `fake-llm-generate` (Generation): chỉ mất **0.152s**
- **Root cause:** Sự cố nằm ở tầng retrieval (`rag_slow`), việc truy vấn tài liệu / vector store bị nghẽn và trễ hơn 2.5 giây, trong khi mô hình LLM vẫn phản hồi nhanh chóng (0.15s).
- **Fix action:** Tắt incident bằng lệnh `python scripts/inject_incident.py --disable`, tối ưu hóa index của Vector DB, cấu hình timeout 1.5s - 2.0s cho bước retrieval.
- **Preventive measure:** Thiết lập cảnh báo symptom-based `high_tail_latency` khi P95 > 3000ms liên tục trong 5 phút; áp dụng caching cho các câu truy vấn phổ biến; thiết lập circuit breaker tự động chuyển sang chế độ fallback trả lời trực tiếp nếu retrieval vượt quá timeout cho phép.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Việc chia nhỏ observation thành các child spans (`retrieval` và `fake-llm-generate`) là quyết định then chốt, giúp định vị chính xác bước gây nghẽn trong quy trình RAG thay vì chỉ biết toàn bộ request bị chậm.
- **Một lỗi/blocker đã gặp:** Ban đầu chạy baseline thì correlation ID bị thiếu (`MISSING`) và PII chưa được scrub.
- **Cách tìm nguyên nhân và xử lý:** Triển khai `CorrelationIdMiddleware` sinh và gắn `req-<8-hex>` vào structlog contextvars, đồng thời bổ sung `scrub_event` vào chuỗi processor của structlog trước khi render JSON.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  1. *Metrics*: Cho cái nhìn vĩ mô, phát hiện triệu chứng (Latency P99 tăng lên 4256ms).
  2. *Logs*: Giúp thu hẹp phạm vi, tìm ra request cụ thể chịu ảnh hưởng thông qua `correlation_id` (`req-a0b69bf4`).
  3. *Traces*: Đi sâu vào bản chất vi mô, phân tích từng span trong request để xác định chính xác bước gây chậm (`retrieval` tốn 2.5s).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Quản lý phiên bản prompt giúp theo dõi được chất lượng câu trả lời theo từng bản release và cho phép rollback tức thì khi prompt mới làm giảm chất lượng hoặc tăng token/chi phí bất thường.
- **Điều quan trọng nhất đã học:** Khả năng quan sát toàn diện (Observability) từ tầng mạng, dữ liệu log đến từng span phân tán là yếu tố sống còn để vận hành hệ thống AI tin cậy trong môi trường production.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Đã hoàn thành 100% tất cả các checkpoint và bài tập theo yêu cầu đề bài.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

